
import asyncio
import logging
import tempfile
import os
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from models import BatchJob, BatchItem, Repo, User
from v2.resume_parser import GeneralExtractor, ExtractCandidateInfo, ResumeParseException
from v2.github_resolver import ResolveRepo
from v2.analysis_service import run_analysis_pipeline, save_analysis_results, run_evaluation_pipeline, save_evaluation_results

logger = logging.getLogger(__name__)

# Use a separate engine for background tasks to avoid sharing sessions across threads incorrectly
# In a real app, this would come from a database config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_PATH = os.path.join(BASE_DIR, "database.db")
engine = create_engine(f"sqlite:///{DATABASE_PATH}")

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
                item.candidate_university = candidate_info.university
                item.github_profile_url = candidate_info.github_profile_url
                session.commit()
                
                # 6. Check GitHub URL
                if not item.github_profile_url:
                    item.status = "error"
                    item.error_message = "Could not resolve GitHub profile. Check resume."
                    item.completed_at = datetime.utcnow()
                    session.commit()
                    return
                
                # 7. Call ResolveRepo
                try:
                    repo_url = ResolveRepo(item.github_profile_url, candidate_info.project_names)
                    item.repo_url = repo_url
                    session.commit()
                except Exception as e:
                    item.status = "error"
                    item.error_message = str(e)
                    item.completed_at = datetime.utcnow()
                    session.commit()
                    return
                
                # 9. Run full analysis pipeline
                # First, get or create user and repo (similar to main.py logic)
                username = repo_url.rstrip("/").split("/")[-2] # Rough username extraction
                repo_name = repo_url.rstrip("/").split("/")[-1]
                
                from v2.analysis_service import get_or_create_user, get_or_create_repo
                user = get_or_create_user(session, username)
                repo = get_or_create_repo(session, user, repo_url, repo_name)
                session.commit()
                
                # If already analyzed, we can link it
                if repo.repo_analysis and repo.repo_evaluation:
                    item.repo_id = repo.id
                    item.status = "completed"
                    item.completed_at = datetime.utcnow()
                    session.commit()
                    return
                
                # Run Analysis
                extracted_data, ai_slop, bad_practices, code_quality, verdict = run_analysis_pipeline(repo_url)
                save_analysis_results(session, repo.id, extracted_data, ai_slop, bad_practices, code_quality, verdict)
                
                # Run Evaluation
                bv, sf, ir, rr, iq = run_evaluation_pipeline(
                    repo_url, repo_name, ai_slop, bad_practices, code_quality, extracted_data, priorities,
                    use_generic_questions=use_generic_questions,
                )
                save_evaluation_results(session, repo.id, bv, sf, ir, rr, iq)
                
                # 10. Update item status
                item.repo_id = repo.id
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
