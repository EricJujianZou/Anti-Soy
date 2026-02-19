"""
resume_parser.py
Handles finding the GitHub corresponding to a person's resume.
resume_parser.py is currently planned to support .pdf, .docx, and .tex files
"""

import pymupdf
import docx
import json
from pathlib import Path

# blacklisted usernames are loaded from file so that they don't clog up the parser source code
GITHUB_USERNAME_BLACKLIST = []
with open("github_username_blacklist.json", "r") as f:
    GITHUB_USERNAME_BLACKLIST = json.load(f)

class struct_resume_dump:
    def __str__(self):
        return f"Plaintext: {self.plaintext}\nHyperlinks: {self.hyperlinks}"
    def __init__(self, plaintext: str, hyperlinks: list[str]):
        self.plaintext = plaintext
        self.hyperlinks = hyperlinks

# dummy exception for now, may include useful data in the future
class ResumeParseException(Exception):
    pass

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
    raise ResumeParseException("Not implemented")

def TexExtractor(tex_path: str) -> struct_resume_dump:
    raise ResumeParseException("Not implemented")

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
    ".tex" : TexExtractor
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
    plaintext_tokens = resume_dump.plaintext.split(" ")
    
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

        
    


# used for unit testing
if __name__ == "__main__":
    while True:
        pdf_file = input("Enter file to parse here: ")
        if Path(pdf_file).exists():
            try:
                resume_dump = GeneralExtractor(pdf_file)
                print("Extracted text:")
                print(resume_dump.plaintext)
                print("Hyperlinks found:")
                for link in resume_dump.hyperlinks:
                    print(f"  {link}")
            except ResumeParseException as e:
                print(f"Error parsing resume: {e}")
        else:
            print("You did NOT provide a valid file")
