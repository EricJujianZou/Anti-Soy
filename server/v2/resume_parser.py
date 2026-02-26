"""
resume_parser.py
Handles finding the GitHub corresponding to a person's resume.
resume_parser.py is currently planned to support .pdf and .docx files
"""

import pymupdf
import docx
import json
import re
from pathlib import Path
from dataclasses import dataclass

PARENT_DIRECTORY = Path(__file__).parent

# blacklisted usernames are loaded from file so that they don't clog up the parser source code
GITHUB_USERNAME_BLACKLIST = []
with open(f"{PARENT_DIRECTORY}/github_username_blacklist.json", "r") as f:
    GITHUB_USERNAME_BLACKLIST = json.load(f)

@dataclass
class CandidateInfo:
    name: str              # first non-empty line of plaintext
    university: str | None # regex match, None if not found
    github_profile_url: str | None  # from existing GithubFromResumeDump, None if raises
    project_names: list[str]        # extracted from Projects section, may be empty

class struct_resume_dump:
    def __str__(self):
        return f"Plaintext: {self.plaintext}\nHyperlinks: {self.hyperlinks}"
    def __init__(self, plaintext: str, hyperlinks: list[str]):
        self.plaintext = plaintext
        self.hyperlinks = hyperlinks

# dummy exception for now, may include useful data in the future
class ResumeParseException(Exception):
    pass

@dataclass
class CandidateInfo:
    name: str              # first non-empty line of plaintext
    university: str | None # regex match, None if not found
    github_profile_url: str | None  # from existing GithubFromResumeDump, None if raises
    project_names: list[str]        # extracted from Projects section, may be empty

def ExtractCandidateInfo(resume_dump: struct_resume_dump) -> CandidateInfo:
    # Name: first non-empty, non-whitespace line of resume_dump.plaintext
    lines = resume_dump.plaintext.splitlines()
    name = "Unknown"
    for line in lines:
        stripped = line.strip()
        if stripped:
            name = stripped
            break
    
    # University: regex scan of full plaintext for patterns
    # We use [^\n\r] to avoid matching across lines
    university_patterns = [
        r"University of [A-Z][^\n\r]+",
        r"[A-Z][^\n\r]+ University",
        r"[A-Z][^\n\r]+ College",
        r"[A-Z][^\n\r]+ Institute of Technology",
        r"\bMIT\b",
        r"\bETH\b",
        r"\bCMU\b",
        r"\bUCLA\b",
        r"\bUC Berkeley\b",
        r"\bStanford\b",
        r"\bHarvard\b"
    ]
    university = None
    for pattern in university_patterns:
        match = re.search(pattern, resume_dump.plaintext, re.IGNORECASE)
        if match:
            university = match.group(0).strip()
            break
            
    # GitHub profile URL
    try:
        github_profile_url = GithubFromResumeDump(resume_dump)
    except ResumeParseException:
        github_profile_url = None
        
    # Project names
    project_names = []
    # scan plaintext for a section header matching "project" (case-insensitive)
    lines = resume_dump.plaintext.splitlines()
    in_projects_section = False
    
    # Common section headers that might follow projects
    next_section_headers = [r"experience", r"education", r"skills", r"awards", r"certificates", r"interests"]
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
            
        if not in_projects_section:
            if re.search(r"projects", stripped, re.IGNORECASE):
                in_projects_section = True
        else:
            # Check if we hit another section header
            is_next_section = False
            for header in next_section_headers:
                if re.fullmatch(header, stripped, re.IGNORECASE) or (stripped.isupper() and len(stripped) > 3):
                    is_next_section = True
                    break
            
            if is_next_section:
                break
            
            # extract subsequent lines that appear to be project titles
            # (short lines, <=6 words, not all lowercase, before the next section header)
            words = stripped.split()
            if 0 < len(words) <= 6 and not stripped.islower():
                # Avoid bullet points or single words that might be noise if they are too short
                # But typically project names are short
                project_names.append(stripped.lstrip('•-* ').strip())
                
    return CandidateInfo(
        name=name,
        university=university,
        github_profile_url=github_profile_url,
        project_names=project_names
    )

def PdfExtractor(pdf_path: str) -> struct_resume_dump:
    text = ""
    hyperlinks = []
    try:
        with pymupdf.open(pdf_path) as pdf:
            for page in pdf:
                text += page.get_text() + "\n"
                for link in page.get_links():
                    hyperlinks.append(link["uri"])

    except Exception as e:
        raise ResumeParseException(f"Error opening PDF file: {e}")
    return struct_resume_dump(text, hyperlinks)

def DocxExtractor(docx_path: str) -> struct_resume_dump:
    text = ""
    hyperlinks = []

    try:
        with open(docx_path, "rb") as f:
            doc = docx.Document(f)
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
                for hyperlink in paragraph.hyperlinks:
                    hyperlinks.append(hyperlink.url)
    except Exception as e:
        raise ResumeParseException(f"Error opening DOCX file: {e}")
    return struct_resume_dump(text, hyperlinks)

"""
Contains all the extractor functions per file type.
Each function must take in a file path (string) as input and output as output a plaintext string representing the plaintext content of the resume.
In addition, the function must return a list of all hyperlinks present in the resume file.
This data will be organized in a struct called struct_resume_dump
Should there ever be an issue with getting the plaintext, the function should throw a ResumeParseException with an appropriate error message.
"""
ExtractorList = {
    ".pdf": PdfExtractor,
    ".docx" : DocxExtractor,
}

"""
Used for abstracting away details about file format when extracting text from resumes
"""
def GeneralExtractor(file_path: str) -> struct_resume_dump:
    extension = Path(file_path).suffix
    if extension in ExtractorList:
        return ExtractorList[extension](file_path)
    raise ResumeParseException(f"Unsupported file type: {extension}")

def GithubFromResumeDump(resume_dump: struct_resume_dump) -> str:
    candidates = []
    proper_profile_links = [] # profile links directly found from the hyperlinks or the plaintext
    implicit_profile_links = [] # profiles that are found by finding repositories linked to a resume and parsing who made the repository from there
    plaintext_tokens = resume_dump.plaintext.split()
    
    # find all instances of github.com links in a resume
    for link in resume_dump.hyperlinks:
        if "github.com" in link:
            candidates.append(link)
    for token in plaintext_tokens:
        token = token.strip()
        if "github.com" in token:
            candidates.append(token)

    for candidate in candidates:
        c_tokens_first_pass = candidate.split("/") 
        c_tokens = []

        # sometimes people will end a link with a "/", meaning the last string of the first pass could potentially be "", do a loop through the first pass to remove empty tokens to account for this
        for token in c_tokens_first_pass:
            token = token.strip()
            if len(token) > 0:
                c_tokens.append(token)

        site_index = c_tokens.index("github.com")
        num_c_tokens = len(c_tokens)
        if site_index == num_c_tokens - 1: # link ends
            pass
        elif site_index == num_c_tokens - 2: # potentially a proper profile link
            username_token = c_tokens[site_index + 1]
            if not (username_token in GITHUB_USERNAME_BLACKLIST): # make sure resume isn't just a link to some github subpage
                # proper link found!
                # also note that we're reconstruction the profile link here because the user could pass something in like "github.com/profile" instead of "https://github.com/profile"
                # this makes it so that we have one consistent link associated with a profile
                if site_index + 2 == num_c_tokens:
                    proper_profile_links.append(f"https://github.com/{username_token}")
                else:
                    implicit_profile_links.append(f"https://github.com/{username_token}")

    # now we need to find out how many times each profile occurs in a resume
    # this is because someone might have multiple githubs listed
    # in this case we choose the one that is most common as that's probably their main account
    best_fit = None
    best_fit_occurences_proper = 0
    best_fit_occurences_implicit = 0
    occurences_proper = {}
    occurences_implicit = {}

    for link in proper_profile_links:
        if not link in occurences_proper:
            occurences_proper[link] = 0
        if not link in occurences_implicit: # when doing implicit links for tiebreakers it's important that the index exists for all possible profiles so we also initialize here as some links might appear in proper links only. in this case they need to have 0 occurences
            occurences_implicit[link] = 0
        occurences_proper[link] += 1
    for link in implicit_profile_links:
        if not link in occurences_implicit:
            occurences_implicit[link] = 0
        occurences_implicit[link] += 1

    for link in proper_profile_links:
        if best_fit == None:
            best_fit = link
            best_fit_occurences_proper = occurences_proper[link]
        elif occurences_proper[link] > best_fit_occurences_proper:
            best_fit = link
            best_fit_occurences_proper = occurences_proper[link]
        elif occurences_proper[link] == best_fit_occurences_proper and occurences_implicit[link] > occurences_implicit[best_fit]: # we use implicit link count as a tiebreaker in this case as more implicit links = more side projects done on a profile = it's likely the main profile for the resume
            best_fit = link
            best_fit_occurences_proper = occurences_proper[link]

    # just in case no occurences of a proper profile were found  
    if best_fit == None:
        for link in implicit_profile_links:
            if best_fit == None:
                best_fit = link
                best_fit_occurences_implicit = occurences_implicit[link]
            elif occurences_implicit[link] > best_fit_occurences_implicit:
                best_fit = link
                best_fit_occurences_implicit = occurences_implicit[link]

    if best_fit == None:
        raise ResumeParseException("No github profiles found in resume")
    return best_fit

def ProfileFromResume(resume_path: str) -> str:
    resume_dump = GeneralExtractor(resume_path)
    return GithubFromResumeDump(resume_dump)
    
def ExtractCandidateInfo(resume_dump: struct_resume_dump) -> CandidateInfo:
    # 1. Name: first non-empty, non-whitespace line
    name = "Unknown Candidate"
    for line in resume_dump.plaintext.split("\n"):
        if line.strip():
            name = line.strip()
            break
            
    # 2. University: regex scan
    university = None
    uni_patterns = [
        r"University of [\w\s]+",
        r"[\w\s]+ University",
        r"[\w\s]+ College",
        r"[\w\s]+ Institute of Technology",
        r"\bMIT\b",
        r"\bETH\b",
        r"\bStanford\b",
        r"\bHarvard\b",
        r"\bBerkeley\b",
    ]
    for pattern in uni_patterns:
        match = re.search(pattern, resume_dump.plaintext, re.IGNORECASE)
        if match:
            university = match.group(0).strip()
            break
            
    # 3. GitHub Profile URL
    github_profile_url = None
    try:
        github_profile_url = GithubFromResumeDump(resume_dump)
    except ResumeParseException:
        pass
        
    # 4. Project Names
    project_names = []
    lines = resume_dump.plaintext.split("\n")
    projects_found = False
    for i, line in enumerate(lines):
        if not projects_found:
            if re.search(r"\bprojects?\b", line, re.IGNORECASE):
                projects_found = True
        else:
            # Look for project titles in subsequent lines
            stripped = line.strip()
            if not stripped:
                continue
            
            # Heuristic for project title: short lines, ≤6 words, not all lowercase, before next section
            # Check if it looks like a section header (all caps or common keywords)
            if re.match(r"^(EDUCATION|EXPERIENCE|SKILLS|LANGUAGES|AWARDS|CERTIFICATIONS|VOLUNTEERING)$", stripped, re.IGNORECASE):
                break
                
            words = stripped.split()
            if len(words) <= 6 and not stripped.islower():
                project_names.append(stripped)
            
            # Stop if we have a few projects or if we've gone too far
            if len(project_names) >= 5:
                break
                
    return CandidateInfo(
        name=name,
        university=university,
        github_profile_url=github_profile_url,
        project_names=project_names
    )
    


# used for unit testing
if __name__ == "__main__":
    while True:
        pdf_file = input("Enter file to parse here: ")
        if Path(pdf_file).exists():
            try:
                resume_dump = GeneralExtractor(pdf_file)
                #print("Extracted text:")
                #print(resume_dump.plaintext)
                print("Hyperlinks found:")
                for link in resume_dump.hyperlinks:
                    print(f"  {link}")
                print(GithubFromResumeDump(resume_dump))
            except ResumeParseException as e:
                print(f"Error parsing resume: {e}")
        else:
            print("You did NOT provide a valid file")
