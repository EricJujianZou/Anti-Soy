"""Quick manual tests for the cross_reference module. Run from server/ directory."""
import asyncio
import json

# Load .env BEFORE importing any v2 modules — config.py reads env vars at import time.
from dotenv import load_dotenv
load_dotenv()

from v2.cross_reference import cross_reference, CandidateInput

# ---------------------------------------------------------------------------
# Shared resume text for test cases 4 & 5
# ---------------------------------------------------------------------------

RESUME_1_TEXT = """
Eric Jujian Zou
LinkedIn · ✉ e2zou@uwaterloo.ca · (+1) 437-360-8683 · GitHub · Devpost

University of Waterloo
Sep 2024 – Apr 2029
BASc Candidate, Electrical Engineering, Honours | GPA: 4.0/4.0
Awards: 2nd in SpurHacks 2025 ($5k funding) | 1st Waterloo Engineering Competition (Junior Design)

SKILLS
ML Tools: LLMs, MCP, RAG, Agents, LangChain, Vector Databases, OpenCV
ML Frameworks: Scikit-learn, NLP, Pandas, TensorFlow, PyTorch
Languages & Frameworks: Python, C++, TypeScript/JavaScript, Java, FastAPI, React, GraphQL
Cloud & MLOps: AWS, GCP, Azure, Docker, Git, SQL, Postgres, Linux

WORK EXPERIENCE
Co-Founder | Anti-Soy
Waterloo, ON, Canada | Jan 2025 - Present
• Interviewed startup founders & engineers from NVIDIA & Apple to validate problem, and developed an ML +
Agentic AI system to help interviewers detect project business need, AI-generated code, and bad SWE practices
• Trained a Random Forest classifier model on 14 code-style features (AST parsing and regex) to achieve an 86%
F1 score in detecting AI-generated code, reducing startup hiring cycles by 2 weeks
• Acquired 82 testers with 12% conversion rate and one real user in 1 month of soft launch with organic outreach

Full-Stack AI Engineer | Revvity Inc.
Toronto, ON, Canada | Sep 2025 - Dec 2025
• Spearheaded a biomarker analysis MVP by iterating through 4 customer-feedback cycles, pivoting from
automated outlier removal to a visual classification system based on user transparency needs
• Secured a Letter of Intent for a pilot automating 60+ reports across 20+ biomarkers by engineering an ML
workflow to process 10+ years of lab data using Python, React, GPT-4o and AWS
• Architected an LLM-as-a-Judge evaluation pipeline for 60+ agents to address user concerns on LLM
transparency, reducing QA costs by 7x through multimodal visual sanity checks for 2,000+ end-users

Technical Lead | Presense
Toronto, ON, Canada | Jun 2025
• Identified and validated a niche in the $17B tech hiring market, and led a 4-person team to build an AI
behavioral interview & training tool for SMBs, saving SMB's $15,000+ per hire
• Architected and built the speech analysis backend using FastAPI, processing real-time audio streams with a
multi-model pipeline (GPT-4o, Gemini, TensorFlow) to score communication skills

Co-Founder | Articula
Toronto ON, Canada | Jul 2023 – Dec 2024
• Identified a gap in communication training for immigrant youth by talking to 30+ users, pitched an NLP AI &
CV (facial mesh node-tracking) practice tool to VCs and secured $4,100 in pre-seed funding
• Accepted into Founders University (Launch pre-accelerator program) and Microsoft for Startups, managing
stakeholder relationships across a 12-week development cycle and received $350,000 cloud credits

PERSONAL PROJECTS
Self-Driving Garbage Truck – C++, OpenCV, RPi, Arduino, UART
Nov 2025
• Engineered an autonomous robotics navigation system in C++, integrating Arduino to process I2C ultrasonic sensor
data to determine possible obstacle-free paths for real-time collision-free routing
• Deployed a YOLOv8 object detection model onto edge hardware (Raspberry Pi), optimizing OpenCV inference
algorithms to achieve 30 FPS visual identification of targets
"""

# Resume 2: has "Expandr" which maps to "promptassist" on GitHub (name change)
RESUME_2_TEXT = """
Eric Jujian Zou
LinkedIn|Website|✉ e2zou@uwaterloo.ca|Github|Devpost

SKILLS
Languages: Java, Python, C++, HTML/CSS, JavaScript, TypeScript, SQL
Tools: Azure DevOps, Power Automate, Postman, .NET, AXE DevTools, Git, Axure RP, SharePoint, Canva
Frameworks & Platforms: React, Angular, Spring Boot, Docker, AWS, Microsoft Azure (OpenAI), STM32

WORK EXPERIENCE
IT Technology Specialist
Ministry of Public and Business Service Delivery – Ontario Public Service
Toronto, ON, Canada
Jan 2025 – Apr 2025
• Enabled firms to submit 500 architectural plans each up to 40 GB annually for approval, by developing a
webform for Ontario's Land Registry Portal using Razor (.cshtml), .NET, and HTML/CSS
• Saved up to $10,000 and increased PM productivity by 50% on 100+ contracts/year by creating a contract
generator in Power Automate and integrating into PMs' workflow in SharePoint
• Saved ministry staff weeks of manual effort valued at approximately $15,400 by developing an automated email
conversion tool using SharePoint and Power Automate
• Improved UX metrics by 25% on Ontario Regulatory Registry site by fixing 30+ defects using Java and Angular
• Reduced 2 WCAG accessibility violations by conducting AODA accessibility testing and pen-testing analysis
on public-facing sites, using Postman and AXE DevTools

Intern Product Manager
Shiyun Technology
Shenzhen, GD, China
Jul 2024 – Aug 2024
• Targeted a 54% reduction in emergency response labor costs by modeling a swim lane diagram for automated
IoT fire hazard evacuation workflows in Axure RP
• Enhanced client understanding of 8 construction monitoring IoT platform features by rewriting the user manual
• Identified 3 feature gaps against AliCloud by conducting competitive analysis on the IoT construction solution

Technical Co-Founder
Articula Inc.
Toronto, ON, Canada
Jul 2023 – Present
• Increased youth confidence by improving communication skills, by designing a computer vision and NLP
feedback tool for engaging daily practices using Python
• Improved pilot users' speaking clarity by 6-10% through reducing filler words, using OpenAI's GPT-3.5 turbo
and AssemblyAI to transcribe speech and to generate feedback
• Raised over $4,000 in funding and secured accelerator admission as one of 272 out of more than 2000 founders
in 5 months, by obtaining letter of intent and pitching at international competitions

PERSONAL PROJECTS
Expandr
Jan 2025 – Present
• Increased LLM accuracy by 57% by developing a prompt automation tool with Python, PySide6, and win32gui
for cross-application snippet injection and OS-level integration
• Reduced pilot users' repetitive typing by 5% by automatically integrating most-used text snippets into workflows
• Maintained <5% CPU usage by engineering keystroke buffer, app focus tracking, and edge case handling

EZTimes
• Reduced procrastination by 20% by developing an automated scheduling application with Pygame and Tkinter
• Implemented 3 custom algorithms to automatically insert tasks into users' daily routine based on task priority
• Won 2nd out of 377 in MetroHacks (Under-18 Education Track) for creative solution and efficient algorithm

Additional Projects
• VitalConnect – IoT wearable for cost-efficient chronic disease monitoring
• EcoConnect – AI-integrated sustainability app to promote sustainable habits
• SimpliFit – Personalized fitness and health planning tool using Java
"""

GITHUB_URL = "https://github.com/EricJujianZou"


async def main():
    print("\n--- Test 1: import OK ---")
    print("cross_reference imported successfully")

    print("\n--- Test 2: low-confidence gate ---")
    result = await cross_reference(CandidateInput(
        name="Test User",
        github="https://github.com/someuser",
        confidence="low",
        resume_text="dummy",
    ))
    print("flags:", result.flags)
    print("error:", result.error)
    assert any("manual_review_required" in f for f in result.flags), "FAIL: expected manual_review_required flag"
    print("PASS")

    print("\n--- Test 3: invalid URL ---")
    result = await cross_reference(CandidateInput(
        name="Test User",
        github="not-a-url",
        confidence="high",
        resume_text="dummy",
    ))
    print("error:", result.error)
    assert result.error and "invalid_github_url" in result.error, "FAIL: expected invalid_github_url error"
    print("PASS")

    # -----------------------------------------------------------------------
    # Test 4: 1 resume project ("Self-Driving Garbage Truck") → expect
    # repos_to_clone padded to 3 via pinned/recent fallback.
    # -----------------------------------------------------------------------
    print("\n--- Test 4: 1 project → padded to 3 repos_to_clone ---")
    result = await cross_reference(CandidateInput(
        name="Eric Jujian Zou",
        github=GITHUB_URL,
        confidence="high",
        resume_text=RESUME_1_TEXT,
    ))
    print(result.model_dump_json(indent=2))
    print("\nSummary:")
    print("  match_summary   :", result.match_summary)
    print("  repos_to_clone  :", result.repos_to_clone)
    print("  flags           :", result.flags)
    print("  error           :", result.error)
    assert result.error is None, f"FAIL: unexpected error: {result.error}"
    assert len(result.repos_to_clone) >= 3, f"FAIL: expected >= 3 repos_to_clone, got {len(result.repos_to_clone)}"
    print("PASS")

    # -----------------------------------------------------------------------
    # Test 5: "Expandr" on resume but "promptassist" on GitHub (name mismatch).
    # The description + tech signals should still produce a match.
    # Also has "EZTimes" which may or may not match.
    # -----------------------------------------------------------------------
    print("\n--- Test 5: name-mismatch 'Expandr' → 'promptassist' ---")
    result = await cross_reference(CandidateInput(
        name="Eric Jujian Zou",
        github=GITHUB_URL,
        confidence="high",
        resume_text=RESUME_2_TEXT,
    ))
    print(result.model_dump_json(indent=2))
    print("\nSummary:")
    print("  match_summary   :", result.match_summary)
    print("  matched_projects:", [(m.resume_project_name, m.repo_name, m.confidence) for m in result.matched_projects])
    print("  repos_to_clone  :", result.repos_to_clone)
    print("  flags           :", result.flags)
    print("  error           :", result.error)
    assert result.error is None, f"FAIL: unexpected error: {result.error}"
    expandr_matched = any(
        m.resume_project_name.lower() == "expandr" and m.repo_name.lower() == "promptassist"
        for m in result.matched_projects
    )
    if expandr_matched:
        print("PASS: 'Expandr' correctly matched to 'promptassist' despite name difference")
    else:
        print("INFO: 'Expandr' did NOT match 'promptassist' — check confidence scores above to diagnose")


asyncio.run(main())
