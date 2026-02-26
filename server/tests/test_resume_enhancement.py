import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to sys.path to allow importing from server.v2
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from server.v2.resume_parser import struct_resume_dump, ExtractCandidateInfo, ResumeParseException
from server.v2.github_resolver import ResolveRepo

class TestResumeEnhancement(unittest.TestCase):

    def test_extract_candidate_info_basic(self):
        plaintext = """John Doe
123 Main St, Anytown, USA
Email: john.doe@example.com
GitHub: github.com/johndoe

EDUCATION
University of California, Berkeley
B.S. in Computer Science

PROJECTS
Awesome Web App
A full-stack web application built with React and Node.js.
Machine Learning Tool
A tool for analyzing large datasets using Python.

EXPERIENCE
Software Engineer at Tech Corp
"""
        hyperlinks = ["https://github.com/johndoe"]
        resume_dump = struct_resume_dump(plaintext, hyperlinks)
        
        info = ExtractCandidateInfo(resume_dump)
        
        self.assertEqual(info.name, "John Doe")
        self.assertEqual(info.university, "University of California, Berkeley")
        self.assertEqual(info.github_profile_url, "https://github.com/johndoe")
        self.assertIn("Awesome Web App", info.project_names)
        self.assertIn("Machine Learning Tool", info.project_names)
        self.assertEqual(len(info.project_names), 2)

    def test_extract_candidate_info_no_projects(self):
        plaintext = """Jane Smith
Jane.Smith@email.com
Stanford University
Experience: ...
"""
        resume_dump = struct_resume_dump(plaintext, [])
        info = ExtractCandidateInfo(resume_dump)
        self.assertEqual(info.name, "Jane Smith")
        self.assertEqual(info.university, "Stanford University")
        self.assertEqual(info.project_names, [])

    def test_extract_candidate_info_acronym_university(self):
        plaintext = """Bob
MIT
Projects:
Cool Bot
"""
        resume_dump = struct_resume_dump(plaintext, [])
        info = ExtractCandidateInfo(resume_dump)
        self.assertEqual(info.university, "MIT")

    def test_extract_candidate_info_relevant_projects(self):
        plaintext = """John Doe
RELEVANT PROJECTS
My Cool Project
A description of my cool project.
Another Project
Another description.
EXPERIENCE
"""
        resume_dump = struct_resume_dump(plaintext, [])
        info = ExtractCandidateInfo(resume_dump)
        self.assertIn("My Cool Project", info.project_names)
        self.assertIn("Another Project", info.project_names)

    @patch('requests.get')
    def test_resolve_repo_match(self, mock_get):
        # Mock GitHub API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "other-repo", "pushed_at": "2023-01-01T00:00:00Z"},
            {"name": "awesome-web-app", "pushed_at": "2022-01-01T00:00:00Z"},
        ]
        mock_get.return_value = mock_response
        
        url = "https://github.com/johndoe"
        projects = ["Awesome Web App", "Some Other Proj"]
        
        resolved_url = ResolveRepo(url, projects)
        self.assertEqual(resolved_url, "https://github.com/johndoe/awesome-web-app")

    @patch('requests.get')
    def test_resolve_repo_fallback(self, mock_get):
        # Mock GitHub API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "most-recent-repo", "pushed_at": "2023-01-01T00:00:00Z"},
            {"name": "older-repo", "pushed_at": "2022-01-01T00:00:00Z"},
        ]
        mock_get.return_value = mock_response
        
        url = "https://github.com/johndoe"
        projects = ["Non Existent Project"]
        
        resolved_url = ResolveRepo(url, projects)
        # Should fallback to the first one (most recent)
        self.assertEqual(resolved_url, "https://github.com/johndoe/most-recent-repo")

    @patch('requests.get')
    def test_resolve_repo_empty_projects(self, mock_get):
        # Mock GitHub API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "most-recent-repo", "pushed_at": "2023-01-01T00:00:00Z"},
        ]
        mock_get.return_value = mock_response
        
        resolved_url = ResolveRepo("https://github.com/johndoe", [])
        self.assertEqual(resolved_url, "https://github.com/johndoe/most-recent-repo")

    @patch('requests.get')
    def test_resolve_repo_api_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_get.return_value = mock_response
        
        with self.assertRaises(ResumeParseException):
            ResolveRepo("https://github.com/nonexistent", [])

if __name__ == '__main__':
    unittest.main()
