"""
amalgam_parser.py
Service for dealing with giant PDFs that are an amalgamation of many resumes
This exists because our first customer is the government who amalgamates PDFs as part of their hiring workflow
"""

import pymupdf
import tempfile
import datetime
import os
import asyncio

from google import genai
from pathlib import Path

gemini_api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=gemini_api_key).aio # making client asynchronous to allow for parallelization

class PageInterval:
    def __init__(self, left, right):
        self.left = left
        self.right = right

# uploads all pages of the amalgam to genai for processing
# input already assumes the amalgam has been separated into pages and the pages have been saved to some temp directory
# returns a list of file handles where the handle to page i lives at output[i]
async def upload_pages(files: list[Path]) -> list[genai.types.File]:
    tasks = []
    for path in files:
        tasks.append(client.files.upload(path))
    return await asyncio.gather(*tasks)

# deletes all outstanding page handles on genai's backend
async def delete_pages(files: list[genai.types.File]):
    tasks = []
    for handle in files:
        tasks.append(client.files.delete(name = handle.name))

    await asyncio.gather(*tasks)

"""
Parses a single page of the amalgam pdf to determine if it is the starter to a PDF
Returns True if page # starts a resume, false otherwise
Since there are multiple pages that could be starters, True/False will be returned by the LLM, from which the function returns True/False
"""
async def kernel_find_resume_starters(page_handles: list[genai.types.File], page: int) -> bool:
    await client.models.generate_content()

"""
Given a resume starts on the first page of a PDF, and some garbage is amalgamated at the end of the resume, this function finds the page at which the resume should end at
The model will use the first page as context, and then incrementally be fed pages, this is done to save on context when doing LLM calls
Instead of returning True/False, a confidence score is assigned to each page by the LLM about how confident it is that a given page is part of the resume
That way, there should be a trend where a definitive sharp drop happens somewhere, at which point the resume can be assumed to have terminated.
This should hopefully remove ambiguity on which page to choose as the ender
After trimming, a new list of pages of every file path that is definitely part of the resume will be returned, which can be assembled by the main function
"""
async def kernel_trim_resume_pages(page_handles: list[genai.types.File], interval: range) -> PageInterval:
    for page in interval:
        pass

async def crack_amalgam_pdf(amalgam_pdf_directory: Path, output_directory: Path):
    timestamp = round(datetime.datetime.now().timestamp())

    with pymupdf.open(amalgam_pdf_directory) as amalgam_pdf:
        files_first_pass = []
        tasks_first_pass = []
        page_handles = None
        first_pass = None

        # for the first pass, each 1 page temp resume file will be put in a directory to be purged once first pass is completed, that way the server doesn't clog up with random files
        # note that second pass code also lies in this with statement as having each page of the amalgam split off is useful for the second pass as it will pass in the first page of an interval and then will pass in the interval PDF page by page
        # if files were destroyed after first pass, work of splitting pages off would have to be redone which is suboptimal 
        with tempfile.TemporaryDirectory as tempdir:
            for i, page in enumerate(amalgam_pdf):
                with pymupdf.open() as staging_pdf:
                    staging_pdf.insert_pdf(amalgam_pdf, from_page=i, to_page=i)
                    staging_pdf.save(tempdir.joinpath(f"page-${i}.pdf"))
                    files_first_pass.append(tempdir.joinpath(f"page-${i}.pdf"))

            page_handles = await upload_pages(files_first_pass) # uploading all pages to genai

            for page, path in enumerate(page_handles): # running all pages through analysis in parallel
                tasks_first_pass.append(kernel_find_resume_starters(page_handles, page))
            first_pass = await asyncio.gather(*tasks_first_pass)
    
            starter_list = [] # page indexes which resumes start on
            for i, is_starter in first_pass: # analyzing the result for each page to create the intervals where resumes may potentially be
                if is_starter:
                    starter_list.append(i)

            # start queuing second pass where we find the end corresponding to each resume starter
            tasks_second_pass = []
            for i in range(1, starter_list):
                tasks_second_pass.append(kernel_trim_resume_pages(page_handles, range(starter_list[i - 1], starter_list[i])))
            tasks_second_pass.append(kernel_trim_resume_pages(starter_list[-1], len(page_handles)))
            second_pass = await asyncio.gather(*tasks_second_pass)

            # construct resumes from page data collected in the second pass (all pages to include in the resume)
            for page_interval in second_pass:
                with pymupdf.open() as staging_pdf:
                    staging_pdf.insert_pdf(amalgam_pdf, from_page=page_interval.left, to_page=page_interval.right)
                    staging_pdf.save(output_directory.joinpath(f"${timestamp}-${page_interval.left}.pdf"))
            
            # delete previously uploaded files
            await delete_pages(page_handles)

# sync wrapper for crack_amalgam_pdf
def crack_amalgam_pdf_sync(amalgam_pdf_directory: Path, output_directory: Path):
    return asyncio.run(crack_amalgam_pdf(amalgam_pdf_directory, output_directory))

# test code
if __name__ == "main":
    while True:
        directory: str = input("Enter pdf directory here: ")
        with tempfile.TemporaryDirectory() as folder:
            try:
                crack_amalgam_pdf(Path(directory), Path(folder))
            except Exception as e:
                print(f"Unable to parse PDF: ${e}")