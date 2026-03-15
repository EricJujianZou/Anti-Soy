
import asyncio
import logging
import tempfile
import os
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from models import BatchJob, BatchItem, BatchItemRepo, Repo, User
from v2.resume_parser import GeneralExtractor, ExtractCandidateInfo, ResumeParseException
from v2.cross_reference import cross_reference, CandidateInput
from v2.analysis_service import (
    run_analysis_pipeline, save_analysis_results,
    run_evaluation_pipeline, save_evaluation_results,
    compute_composite_score, compute_tech_match_penalty,
    aggregate_tech_stack,
)
from v2.data_extractor import detect_deployment_signals
from v2.schemas import DEFAULT_PRIORITIES, ScoringConfig

logger = logging.getLogger(__name__)

# Separate engine for background tasks to avoid sharing sessions across threads
engine = create_engine(
    os.environ["DATABASE_URL"],
    pool_pre_ping=True,
    pool_size=1,          # Cloud Tasks gives horizontal scale; 8 instances × 2 max = 16 connections (fits Neon free tier)
    max_overflow=1,
)

# Keep per-batch DB pressure below pool limits to avoid QueuePool timeouts.
BATCH_ITEM_CONCURRENCY = int(os.getenv("BATCH_ITEM_CONCURRENCY", "4"))

async def process_batch(batch_id: str, priorities: Optional[list[str]] = None, use_generic_questions: bool = False):
    """
    Background task to process a batch of resumes.
    scoring_config is read from the BatchJob record — not passed as an arg to avoid serialization issues.
    """
    logger.info(f"Starting batch processing for {batch_id}")

    with Session(engine) as session:
        batch_job = session.query(BatchJob).filter(BatchJob.id == batch_id).first()
        if not batch_job:
            logger.error(f"Batch job {batch_id} not found")
            return

        use_generic_questions = bool(batch_job.use_generic_questions)
        batch_job.status = "running"
        session.commit()

        # Process items with bounded concurrency to avoid DB pool exhaustion.
        item_ids = [item.id for item in batch_job.items if item.status in ["pending", "running"]]
        semaphore = asyncio.Semaphore(max(1, BATCH_ITEM_CONCURRENCY))

        async def _run_item(item_id: int):
            async with semaphore:
                await process_single_item(item_id, batch_id, priorities, use_generic_questions)

        results = await asyncio.gather(*[_run_item(item_id) for item_id in item_ids], return_exceptions=True)
        for item_id, result in zip(item_ids, results):
            if isinstance(result, Exception):
                logger.exception(f"Batch item {item_id} failed with unhandled exception: {result}")
        
        # Reload to check status
        session.refresh(batch_job)
        batch_job.status = "completed"
        session.commit()
        logger.info(f"Completed batch processing for {batch_id}")

async def process_single_item(item_id: int, batch_id: str, priorities: Optional[list[str]] = None, use_generic_questions: bool = False):
    """
    Processes a single resume item.
    scoring_config is read from the BatchJob within this session.
    """
    import json as _json
    # Create a new session for this item to ensure thread safety/isolation
    with Session(engine) as session:
        item = session.query(BatchItem).filter(BatchItem.id == item_id).first()
        if not item:
            return

        # Load scoring_config from BatchJob; fall back to defaults if not present
        batch_job = session.query(BatchJob).filter(BatchJob.id == batch_id).first()
        scoring_config_dict = ScoringConfig().model_dump()
        if batch_job and batch_job.scoring_config:
            try:
                scoring_config_dict = _json.loads(batch_job.scoring_config)
            except Exception:
                pass  # keep defaults
            
        item.status = "running"
        session.commit()
        
        try:
            # 2. Write file_bytes to tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=item.file_ext) as temp:
                temp.write(item.file_bytes)
                temp_path = temp.name
            
            try:
                # 3. Call GeneralExtractor
                resume_dump = GeneralExtractor(temp_path)
                
                # 4. Call ExtractCandidateInfo
                candidate_info = ExtractCandidateInfo(resume_dump)
                
                # 5. Update item fields
                item.candidate_name = candidate_info.name
                item.github_profile_url = candidate_info.github_profile_url
                session.commit()
                
                # 6. Check GitHub URL
                if not item.github_profile_url:
                    item.status = "error"
                    item.error_message = "Could not resolve GitHub profile. Check resume."
                    item.completed_at = datetime.utcnow()
                    session.commit()
                    return

                # 7. Cross-reference resume projects against GitHub repos.
                # NOTE: confidence defaults to "high" here as a placeholder until the
                # upstream PDF intake layer is implemented and provides a real value.
                # NOTE: resume_dump.plaintext is the raw resume text required by the
                # LLM project extraction step (Step 3 in the cross_reference pipeline).
                candidate_input = CandidateInput(
                    name=candidate_info.name,
                    github=item.github_profile_url,
                    pages=[],
                    confidence="high",  # TODO: wire in actual confidence from upstream PDF intake layer
                    resume_text=resume_dump.plaintext,
                )

                try:
                    person = await cross_reference(candidate_input)
                except Exception as e:
                    session.rollback()
                    item.status = "error"
                    item.error_message = f"Cross-reference failed: {e}"
                    item.completed_at = datetime.utcnow()
                    session.commit()
                    return

                if person.error:
                    item.status = "error"
                    item.error_message = person.error
                    item.completed_at = datetime.utcnow()
                    session.commit()
                    return

                if not person.repos_to_clone:
                    item.status = "error"
                    item.error_message = "No repositories found to analyze for this candidate."
                    item.completed_at = datetime.utcnow()
                    session.commit()
                    return

                if person.flags:
                    logger.info(f"Cross-reference flags for item {item_id}: {person.flags}")

                # 8. Run analysis on all repos in repos_to_clone.
                # item.repo_id is linked to the primary (first/highest-confidence) repo.
                from v2.analysis_service import get_or_create_user, get_or_create_repo
                primary_repo_id: int | None = None
                primary_user = None

                for repo_position, repo_url in enumerate(person.repos_to_clone):
                    url_parts = repo_url.rstrip("/").split("/")
                    repo_username = url_parts[-2]
                    repo_name = url_parts[-1]

                    user = get_or_create_user(session, repo_username)
                    repo = get_or_create_repo(session, user, repo_url, repo_name)
                    session.commit()

                    # Track primary repo (first in list) for item linkage
                    if primary_repo_id is None:
                        primary_repo_id = repo.id
                        primary_user = user
                        item.repo_url = repo_url
                        session.commit()

                    # Link this repo to the batch item via the join table
                    existing_link = session.query(BatchItemRepo).filter(
                        BatchItemRepo.batch_item_id == item.id,
                        BatchItemRepo.repo_id == repo.id,
                    ).first()
                    if not existing_link:
                        session.add(BatchItemRepo(
                            batch_item_id=item.id,
                            repo_id=repo.id,
                            position=repo_position,
                        ))
                        session.commit()

                    # Skip repos that are already fully analyzed
                    if repo.repo_analysis and repo.repo_evaluation:
                        logger.info(f"Cache hit for repo {repo_url} — skipping clone and analysis")
                        continue

                    try:
                        effective_priorities = priorities or DEFAULT_PRIORITIES
                        extracted_data, ai_slop, bad_practices, code_quality, verdict = run_analysis_pipeline(repo_url)
                        save_analysis_results(session, repo.id, extracted_data, ai_slop, bad_practices, code_quality, verdict)

                        # Detect deployment signals from already-extracted data (no re-clone)
                        deployment = detect_deployment_signals(extracted_data)

                        bv, sf, ir, rr, iq = run_evaluation_pipeline(
                            repo_url, repo_name, ai_slop, bad_practices, code_quality, extracted_data, effective_priorities,
                            skip_questions=True,  # questions are generated on-demand per batch item
                        )
                        save_evaluation_results(session, repo.id, bv, sf, ir, rr, iq)

                        # Compute tech match penalty for this repo
                        required_tech = scoring_config_dict.get("required_tech", {})
                        tech_penalty = compute_tech_match_penalty(
                            repo_languages=extracted_data.languages or {},
                            repo_dependencies=extracted_data.dependencies or [],
                            ai_slop_score=ai_slop.score,
                            required_tech=required_tech,
                        )

                        # Compute composite score for this repo (stored for candidate aggregation below)
                        import json as _json2
                        bad_practices_findings = []
                        try:
                            bp_data = _json2.loads(bad_practices.model_dump_json())
                            bad_practices_findings = bp_data.get("findings", [])
                        except Exception:
                            pass

                        originality_score = 0.5
                        if bv and isinstance(bv, dict):
                            originality_score = bv.get("originality_score", 0.5)

                        repo_composite = compute_composite_score(
                            ai_slop_score=ai_slop.score,
                            bad_practices_score=bad_practices.score,
                            code_quality_score=code_quality.score,
                            originality_score=originality_score,
                            bad_practices_findings=bad_practices_findings,
                            scoring_config=scoring_config_dict,
                            shipped_to_prod=deployment.get("shipped_to_prod", False),
                            tech_match_penalty=tech_penalty,
                        )
                        logger.debug(f"Repo {repo_name}: composite_score={repo_composite}, shipped_to_prod={deployment.get('shipped_to_prod')}")
                    except Exception as e:
                        logger.warning(f"Analysis failed for repo {repo_url} (item {item_id}): {e}")
                        session.rollback()  # Clear aborted transaction so the next repo can proceed
                        # Continue with remaining repos even if one fails

                # 10. Update item status
                item.repo_id = primary_repo_id

                # Pre-populate generic questions on the primary User so the UI never shows a Generate button.
                # Only set if not already generated (don't overwrite real questions with generic ones).
                if use_generic_questions and primary_user and not primary_user.interview_questions:
                    from prompt_modules import HARDCODED_INTERVIEW_QUESTIONS
                    import json as _json
                    primary_user.interview_questions = _json.dumps(HARDCODED_INTERVIEW_QUESTIONS)

                item.status = "completed"
                item.completed_at = datetime.utcnow()
                session.commit()
                
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        except ResumeParseException as e:
            session.rollback()
            item.status = "error"
            item.error_message = f"Failed to read resume file: {str(e)}"
            item.completed_at = datetime.utcnow()
            session.commit()
        except Exception as e:
            logger.exception(f"Error processing item {item_id}")
            session.rollback()
            item.status = "error"
            item.error_message = f"An unexpected error occurred: {str(e)}"
            item.completed_at = datetime.utcnow()
            session.commit()
