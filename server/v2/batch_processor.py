
import asyncio
import logging
import tempfile
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from models import BatchJob, BatchItem, Repo, User
from v2.resume_parser import GeneralExtractor, ExtractCandidateInfo, ResumeParseException
from v2.cross_reference import cross_reference, CandidateInput
from v2.analysis_service import run_analysis_pipeline, save_analysis_results, run_evaluation_pipeline, save_evaluation_results

logger = logging.getLogger(__name__)

# Separate engine for background tasks to avoid sharing sessions across threads
engine = create_engine(
    os.environ["DATABASE_URL"],
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=5,
)

async def process_batch(batch_id: str, priorities: list[str] = None, use_generic_questions: bool = False):
    """
    Background task to process a batch of resumes.
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

        # Process items concurrently
        tasks = [process_single_item(item.id, priorities, use_generic_questions) for item in batch_job.items if item.status in ["pending", "running"]]
        await asyncio.gather(*tasks)
        
        # Reload to check status
        session.refresh(batch_job)
        batch_job.status = "completed"
        session.commit()
        logger.info(f"Completed batch processing for {batch_id}")

async def process_single_item(item_id: int, priorities: list[str] = None, use_generic_questions: bool = False):
    """
    Processes a single resume item.
    """
    # Create a new session for this item to ensure thread safety/isolation
    with Session(engine) as session:
        item = session.query(BatchItem).filter(BatchItem.id == item_id).first()
        if not item:
            return
            
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

                for repo_url in person.repos_to_clone:
                    url_parts = repo_url.rstrip("/").split("/")
                    repo_username = url_parts[-2]
                    repo_name = url_parts[-1]

                    user = get_or_create_user(session, repo_username)
                    repo = get_or_create_repo(session, user, repo_url, repo_name)
                    session.commit()

                    # Track primary repo (first in list) for item linkage
                    if primary_repo_id is None:
                        primary_repo_id = repo.id
                        item.repo_url = repo_url
                        session.commit()

                    # Skip repos that are already fully analyzed
                    if repo.repo_analysis and repo.repo_evaluation:
                        continue

                    try:
                        extracted_data, ai_slop, bad_practices, code_quality, verdict = run_analysis_pipeline(repo_url)
                        save_analysis_results(session, repo.id, extracted_data, ai_slop, bad_practices, code_quality, verdict)

                        bv, sf, ir, rr, iq = run_evaluation_pipeline(
                            repo_url, repo_name, ai_slop, bad_practices, code_quality, extracted_data, priorities,
                            use_generic_questions=use_generic_questions,
                        )
                        save_evaluation_results(session, repo.id, bv, sf, ir, rr, iq)
                    except Exception as e:
                        logger.warning(f"Analysis failed for repo {repo_url} (item {item_id}): {e}")
                        # Continue with remaining repos even if one fails

                # 10. Update item status
                item.repo_id = primary_repo_id
                item.status = "completed"
                item.completed_at = datetime.utcnow()
                session.commit()
                
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        except ResumeParseException as e:
            item.status = "error"
            item.error_message = f"Failed to read resume file: {str(e)}"
            item.completed_at = datetime.utcnow()
            session.commit()
        except Exception as e:
            logger.exception(f"Error processing item {item_id}")
            item.status = "error"
            item.error_message = f"An unexpected error occurred: {str(e)}"
            item.completed_at = datetime.utcnow()
            session.commit()
