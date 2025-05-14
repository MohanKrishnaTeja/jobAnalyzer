import re
import logging
import pandas as pd
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from django.conf import settings
from jobspy import scrape_jobs
from google import generativeai as genai
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict
from collections import Counter

# Logging
logger = logging.getLogger(__name__)

# Configure Gemini
try:
    GEMINI_API_KEY = settings.GEMINI_API_KEY
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash")
except AttributeError:
    logger.error("GEMINI_API_KEY not found in Django settings.")
    gemini_model = None
except Exception as e:
    logger.error(f"Error configuring Gemini: {e}")
    gemini_model = None

# Prompt templates
CURRICULUM_SKILLS_PROMPT = """
Analyze the following curriculum and extract all technical and non-technical skills.
Return ONLY a comma-separated list of skills. Do not include any other text.
Here is the curriculum:
"""

JOB_SKILLS_ANALYSIS_PROMPT = """
Analyze these job descriptions and identify the most commonly required technical and non-technical skills.
Return ONLY a comma-separated list of the top skills. Do not include any other text.
Here are the job descriptions:
"""

PROJECT_GENERATION_PROMPT = """
Based on the following skill: {skill}
Generate a project that demonstrates this skill.
Respond in English (US).
Provide ONLY a table with the following columns: "Project Title", "Project Description", "Technologies to be Used", "Implementation Brief", and "% Chance of Shortlisting".
Do NOT include any introductory text, concluding text, or any other content outside of this table.
"""

MAJOR_PROJECT_PROMPT = """
Based on the following combined skills: {skills}
Generate a comprehensive project that demonstrates these skills together.
Respond in English (US).
Provide ONLY a table with the following columns: "Project Title", "Project Description", "Technologies to be Used", "Implementation Brief", and "% Chance of Shortlisting".
Do NOT include any introductory text, concluding text, or any other content outside of this table.
"""

SKILL_COMPARISON_PROMPT = """
Compare these two sets of skills:
Curriculum Skills: {curriculum_skills}
Job Market Skills: {job_market_skills}

Identify which skills from the job market are missing in the curriculum.
Return ONLY a comma-separated list of missing skills. Do not include any other text.
"""

JOB_ROLE_PROMPT = """
Based on the following skills:
{skills}

Identify the top 3-4 most relevant job roles that match these skills.
Return ONLY a comma-separated list of job roles. For example: Data Analyst, Business Intelligence Analyst, Data Scientist
Do NOT include any other text or explanation.
"""

class CurriculumAnalysisSerializer(serializers.Serializer):
    curriculum_text = serializers.CharField(required=True)

class JobAnalysisSerializer(serializers.Serializer):
    skills = serializers.ListField(
        child=serializers.CharField(),
        required=True
    )

class ProjectGenerationSerializer(serializers.Serializer):
    skills = serializers.ListField(
        child=serializers.CharField(),
        required=True
    )

def extract_skills_from_text(text: str, prompt_template: str) -> List[str]:
    if not gemini_model:
        return []
    try:
        prompt = prompt_template + text
        response = gemini_model.generate_content(prompt)
        skills = [skill.strip() for skill in response.text.split(',') if skill.strip()]
        return skills
    except Exception as e:
        logger.error(f"Error extracting skills: {e}")
        return []

def analyze_job_descriptions(job_descriptions: List[str]) -> List[str]:
    if not gemini_model:
        return []
    try:
        combined_descriptions = "\n\n".join(job_descriptions)
        prompt = JOB_SKILLS_ANALYSIS_PROMPT + combined_descriptions
        response = gemini_model.generate_content(prompt)
        skills = [skill.strip() for skill in response.text.split(',') if skill.strip()]
        return skills
    except Exception as e:
        logger.error(f"Error analyzing job descriptions: {e}")
        return []

def generate_project_for_skill(skill: str) -> str:
    if not gemini_model:
        return "Error: Gemini model not configured"
    try:
        prompt = PROJECT_GENERATION_PROMPT.format(skill=skill)
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error generating project: {e}")
        return f"Error generating project: {e}"

def generate_major_project(skills: List[str]) -> str:
    if not gemini_model:
        return "Error: Gemini model not configured"
    try:
        prompt = MAJOR_PROJECT_PROMPT.format(skills=", ".join(skills))
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error generating major project: {e}")
        return f"Error generating major project: {e}"

def compare_skills(curriculum_skills: List[str], job_market_skills: List[str]) -> List[str]:
    if not gemini_model:
        return []
    try:
        prompt = SKILL_COMPARISON_PROMPT.format(
            curriculum_skills=", ".join(curriculum_skills),
            job_market_skills=", ".join(job_market_skills)
        )
        response = gemini_model.generate_content(prompt)
        missing_skills = [skill.strip() for skill in response.text.split(',') if skill.strip()]
        return missing_skills
    except Exception as e:
        logger.error(f"Error comparing skills: {e}")
        return []

def identify_job_roles(skills: List[str]) -> List[str]:
    if not gemini_model:
        return []
    try:
        skills_text = ", ".join(skills)
        prompt = JOB_ROLE_PROMPT.format(skills=skills_text)
        response = gemini_model.generate_content(prompt)
        roles = [role.strip() for role in response.text.split(',') if role.strip()]
        return roles[:4]  # Return top 4 roles
    except Exception as e:
        logger.error(f"Error identifying job roles: {e}")
        return []

class CurriculumAnalysisView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = CurriculumAnalysisSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        curriculum_text = serializer.validated_data['curriculum_text']
        extracted_skills = extract_skills_from_text(curriculum_text, CURRICULUM_SKILLS_PROMPT)

        return Response({
            "extracted_skills": extracted_skills
        }, status=status.HTTP_200_OK)

class JobAnalysisView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = JobAnalysisSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        skills = serializer.validated_data['skills']
        job_location = "India"  # Hardcoded location
        platforms_to_scrape = ["indeed", "linkedin", "google"]
        
        # First, identify relevant job roles from skills
        job_roles = identify_job_roles(skills)
        if not job_roles:
            return Response({"error": "Could not identify job roles from skills"}, status=status.HTTP_400_BAD_REQUEST)

        all_jobs = pd.DataFrame()
        results_to_fetch_per_term = 50

        try:
            # Scrape jobs based on identified roles
            for role in job_roles:
                search_term = f"entry level {role}"
                jobs_df = scrape_jobs(
                    site_name=platforms_to_scrape,
                    search_term=search_term,
                    location=job_location,
                    results_wanted=results_to_fetch_per_term,
                    country_indeed="India",
                    linkedin_fetch_description=True,
                    description_format="markdown"
                )
                
                if jobs_df is not None and not jobs_df.empty:
                    if all_jobs.empty:
                        all_jobs = jobs_df
                    else:
                        all_jobs = pd.concat([all_jobs, jobs_df], ignore_index=True)

            if all_jobs.empty:
                return Response({"message": "No jobs found"}, status=status.HTTP_404_NOT_FOUND)

            # Get top 20 jobs
            all_jobs.drop_duplicates(subset=['title', 'company', 'location', 'description'], keep='first', inplace=True)
            top_jobs = all_jobs.head(20)

            # Format jobs for response
            formatted_jobs = []
            for _, job in top_jobs.iterrows():
                job_data = {
                    "title": job.get("title", "N/A"),
                    "company": job.get("company", "N/A"),
                    "location": job.get("location", "N/A"),
                    "description": job.get("description", "N/A"),
                    "job_url": job.get("job_url", "N/A"),
                    "source_platform": job.get("site", "N/A"),
                    "posted_date": job.get("posted_date", "N/A"),
                    "salary": job.get("salary", "N/A")
                }
                formatted_jobs.append(job_data)

            # Get top 10-12 job descriptions for analysis
            job_descriptions = top_jobs.head(12)['description'].tolist()
            
            # Analyze job descriptions to extract common skills
            common_skills = analyze_job_descriptions(job_descriptions)

            return Response({
                "identified_roles": job_roles,
                "jobs": formatted_jobs,
                "common_skills": common_skills
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in job analysis: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProjectGenerationView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = ProjectGenerationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        skills = serializer.validated_data['skills']

        try:
            # Generate projects for each skill
            mini_projects = {}
            for skill in skills:
                project = generate_project_for_skill(skill)
                mini_projects[skill] = project

            # Generate major project combining all skills
            major_project = generate_major_project(skills)

            return Response({
                "mini_projects": mini_projects,
                "major_project": major_project
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in project generation: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SkillComparisonView(APIView):
    def post(self, request, *args, **kwargs):
        curriculum_skills = request.data.get('curriculum_skills', [])
        job_market_skills = request.data.get('job_market_skills', [])

        if not curriculum_skills or not job_market_skills:
            return Response(
                {"error": "Both curriculum_skills and job_market_skills are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        missing_skills = compare_skills(curriculum_skills, job_market_skills)

        return Response({
            "missing_skills": missing_skills
        }, status=status.HTTP_200_OK)
