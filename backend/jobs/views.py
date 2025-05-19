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
from django.http import StreamingHttpResponse, HttpRequest
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
import time

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

JOB_BASED_PROJECT_PROMPT = """
Based on the following job market summary:
{job_summary}

Generate a comprehensive project that would make a candidate stand out for these roles.
The project should:
1. Address key technical requirements
2. Demonstrate relevant soft skills
3. Showcase industry-standard practices
4. Be suitable for the specified experience level
5. Include modern technologies mentioned in the requirements

Respond in English (US).
Provide ONLY a table with the following columns: "Project Title", "Project Description", "Technologies to be Used", "Implementation Brief", "Key Skills Demonstrated", and "% Chance of Shortlisting".
Do NOT include any introductory text, concluding text, or any other content outside of this table.
"""

JOB_BASED_MINI_PROJECTS_PROMPT = """
Based on the following job market summary:
{job_summary}

Generate 3 mini projects that would help a candidate build their skills for these roles.
Each project should:
1. Focus on different aspects of the job requirements
2. Be completable in 2-4 weeks
3. Use relevant technologies
4. Demonstrate practical skills

For each project, provide:
1. Project Title
2. Brief Description
3. Key Skills to Develop
4. Technologies to Use
5. Implementation Steps
6. Expected Learning Outcomes

Format the response as a structured list of projects.
"""

SKILL_COMPARISON_PROMPT = """
Compare these two sets of skills:
Curriculum Skills: {curriculum_skills}
Job Market Skills: {job_market_skills}

Identify which skills from the job market are missing in the curriculum.
Return ONLY a comma-separated list of missing skills. Do not include any other text.
"""

EXTRACT_SKILLS_FROM_SUMMARY_PROMPT = """
Extract all technical and non-technical skills from the following job market summary.
Return ONLY a comma-separated list of skills. Do not include any other text.
Here is the summary:
{job_summary}
"""

JOB_ROLE_PROMPT = """
Based on the following skills:
{skills}

Identify the top 3-4 most relevant job roles that match these skills.
Return ONLY a comma-separated list of job roles. For example: Data Analyst, Business Intelligence Analyst, Data Scientist
Do NOT include any other text or explanation.
"""

JOB_SUMMARY_PROMPT = """
Analyze these job descriptions and create a comprehensive summary that includes:
1. Common technical skills and requirements
2. Common soft skills and qualifications
3. Typical responsibilities and duties
4. Educational requirements
5. Experience requirements

Format the response as a structured summary with clear sections.
Here are the job descriptions:
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

def generate_job_summary(job_descriptions: List[str]) -> str:
    if not gemini_model:
        return "Error: Gemini model not configured"
    try:
        combined_descriptions = "\n\n".join(job_descriptions)
        prompt = JOB_SUMMARY_PROMPT + combined_descriptions
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error generating job summary: {e}")
        return f"Error generating job summary: {e}"

def generate_job_based_project(job_summary: str) -> str:
    if not gemini_model:
        return "Error: Gemini model not configured"
    try:
        prompt = JOB_BASED_PROJECT_PROMPT.format(job_summary=job_summary)
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error generating job-based project: {e}")
        return f"Error generating job-based project: {e}"

def generate_job_based_mini_projects(job_summary: str) -> str:
    if not gemini_model:
        return "Error: Gemini model not configured"
    try:
        prompt = JOB_BASED_MINI_PROJECTS_PROMPT.format(job_summary=job_summary)
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error generating job-based mini projects: {e}")
        return f"Error generating job-based mini projects: {e}"

def extract_skills_from_summary(job_summary: str) -> List[str]:
    if not gemini_model:
        return []
    try:
        prompt = EXTRACT_SKILLS_FROM_SUMMARY_PROMPT.format(job_summary=job_summary)
        response = gemini_model.generate_content(prompt)
        skills = [skill.strip() for skill in response.text.split(',') if skill.strip()]
        return skills
    except Exception as e:
        logger.error(f"Error extracting skills from summary: {e}")
        return []

class SkillComparisonSerializer(serializers.Serializer):
    curriculum_skills = serializers.ListField(
        child=serializers.CharField(),
        required=True
    )
    job_summary = serializers.CharField(required=True)

class SkillComparisonView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = SkillComparisonSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        curriculum_skills = serializer.validated_data['curriculum_skills']
        job_summary = serializer.validated_data['job_summary']

        try:
            # Extract skills from job summary
            job_market_skills = extract_skills_from_summary(job_summary)
            
            if not job_market_skills:
                return Response(
                    {"error": "Could not extract skills from job summary"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Compare skills
            missing_skills = compare_skills(curriculum_skills, job_market_skills)

            return Response({
                "missing_skills": missing_skills,
                "extracted_job_market_skills": job_market_skills  # Added for transparency
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in skill comparison: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            
            # Generate comprehensive job summary instead of just common skills
            job_summary = generate_job_summary(job_descriptions)

            return Response({
                "identified_roles": job_roles,
                "jobs": formatted_jobs,
                "job_summary": job_summary
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
        job_summary = request.data.get('job_summary')

        try:
            if job_summary:
                # Generate projects based on job summary
                major_project = generate_job_based_project(job_summary)
                mini_projects = generate_job_based_mini_projects(job_summary)
            else:
                # Fallback to original skill-based generation
                mini_projects = {}
                for skill in skills:
                    project = generate_project_for_skill(skill)
                    mini_projects[skill] = project
                major_project = generate_major_project(skills)

            return Response({
                "mini_projects": mini_projects,
                "major_project": major_project
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in project generation: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class CompleteAnalysisStreamView(View):
    def get(self, request, *args, **kwargs):
        curriculum_text = request.GET.get('curriculum_text')
        if not curriculum_text:
            return StreamingHttpResponse(
                f"data: {json.dumps({'error': 'curriculum_text is required'})}\n\n",
                content_type='text/event-stream'
            )

        def event_stream():
            try:
                # Step 1: Extract skills from curriculum
                yield f"data: {json.dumps({'step': 'extracting_skills', 'message': 'Analyzing your curriculum...'})}\n\n"
                curriculum_skills = extract_skills_from_text(curriculum_text, CURRICULUM_SKILLS_PROMPT)
                if not curriculum_skills:
                    yield f"data: {json.dumps({'error': 'Could not extract skills from curriculum'})}\n\n"
                    return
                yield f"data: {json.dumps({'step': 'skills_extracted', 'data': curriculum_skills})}\n\n"

                # Step 2: Identify relevant job roles
                yield f"data: {json.dumps({'step': 'identifying_roles', 'message': 'Identifying relevant job roles...'})}\n\n"
                job_roles = identify_job_roles(curriculum_skills)
                if not job_roles:
                    yield f"data: {json.dumps({'error': 'Could not identify relevant job roles'})}\n\n"
                    return
                yield f"data: {json.dumps({'step': 'roles_identified', 'data': job_roles})}\n\n"

                # Step 3: Fetch jobs for each role, yield fetching_jobs for each
                yield f"data: {json.dumps({'step': 'fetching_jobs', 'message': 'Fetching relevant job listings...'})}\n\n"
                job_location = "India"
                platforms_to_scrape = ["indeed", "linkedin", "google"]
                all_jobs = pd.DataFrame()
                results_to_fetch_per_term = 50

                for role in job_roles:
                    yield f"data: {json.dumps({'step': 'fetching_jobs', 'message': f'Searching for {role} positions...'})}\n\n"
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
                    yield f"data: {json.dumps({'error': 'No jobs found'})}\n\n"
                    return

                # Step 4: Format jobs and yield jobs_fetched
                all_jobs.drop_duplicates(subset=['title', 'company', 'location', 'description'], keep='first', inplace=True)
                top_jobs = all_jobs.head(20)
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
                yield f"data: {json.dumps({'step': 'jobs_fetched', 'data': formatted_jobs})}\n\n"

                # Step 5: Generate job summary
                yield f"data: {json.dumps({'step': 'generating_summary', 'message': 'Analyzing job requirements...'})}\n\n"
                job_descriptions = top_jobs.head(12)['description'].tolist()
                job_summary = generate_job_summary(job_descriptions)
                yield f"data: {json.dumps({'step': 'summary_generated', 'data': job_summary})}\n\n"

                # Step 6: Analyze skill gaps
                yield f"data: {json.dumps({'step': 'analyzing_gaps', 'message': 'Analyzing skill gaps...'})}\n\n"
                job_market_skills = extract_skills_from_summary(job_summary)
                missing_skills = compare_skills(curriculum_skills, job_market_skills)
                yield f"data: {json.dumps({'step': 'gaps_analyzed', 'data': {'missing_skills': missing_skills, 'job_market_skills': job_market_skills}})}\n\n"

                # Step 7: Generate projects
                yield f"data: {json.dumps({'step': 'generating_projects', 'message': 'Generating project recommendations...'})}\n\n"
                major_project = generate_job_based_project(job_summary)
                # Convert markdown table to point-wise format
                major_project_points = markdown_table_to_points(major_project)
                yield f"data: {json.dumps({'step': 'major_project_generated', 'data': major_project_points})}\n\n"
                mini_projects = generate_job_based_mini_projects(job_summary)
                yield f"data: {json.dumps({'step': 'mini_projects_generated', 'data': mini_projects})}\n\n"

                # Step 8: Complete
                yield f"data: {json.dumps({'step': 'complete', 'message': 'Analysis complete!'})}\n\n"

            except Exception as e:
                logger.error(f"Error in complete analysis: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Accept'
        return response

class CompleteAnalysisView(APIView):
    def get(self, request, *args, **kwargs):
        curriculum_text = request.GET.get('curriculum_text')
        if not curriculum_text:
            return Response(
                {"error": "curriculum_text is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        def event_stream():
            try:
                # Step 1: Extract skills from curriculum
                yield f"data: {json.dumps({'step': 'extracting_skills', 'message': 'Analyzing your curriculum...'})}\n\n"
                curriculum_skills = extract_skills_from_text(curriculum_text, CURRICULUM_SKILLS_PROMPT)
                if not curriculum_skills:
                    yield f"data: {json.dumps({'error': 'Could not extract skills from curriculum'})}\n\n"
                    return
                yield f"data: {json.dumps({'step': 'skills_extracted', 'data': curriculum_skills})}\n\n"

                # Step 2: Identify relevant job roles
                yield f"data: {json.dumps({'step': 'identifying_roles', 'message': 'Identifying relevant job roles...'})}\n\n"
                job_roles = identify_job_roles(curriculum_skills)
                if not job_roles:
                    yield f"data: {json.dumps({'error': 'Could not identify relevant job roles'})}\n\n"
                    return
                yield f"data: {json.dumps({'step': 'roles_identified', 'data': job_roles})}\n\n"

                # Step 3: Fetch jobs for each role, yield fetching_jobs for each
                yield f"data: {json.dumps({'step': 'fetching_jobs', 'message': 'Fetching relevant job listings...'})}\n\n"
                job_location = "India"
                platforms_to_scrape = ["indeed", "linkedin", "google"]
                all_jobs = pd.DataFrame()
                results_to_fetch_per_term = 50

                for role in job_roles:
                    yield f"data: {json.dumps({'step': 'fetching_jobs', 'message': f'Searching for {role} positions...'})}\n\n"
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
                    yield f"data: {json.dumps({'error': 'No jobs found'})}\n\n"
                    return

                # Step 4: Format jobs and yield jobs_fetched
                all_jobs.drop_duplicates(subset=['title', 'company', 'location', 'description'], keep='first', inplace=True)
                top_jobs = all_jobs.head(20)
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
                yield f"data: {json.dumps({'step': 'jobs_fetched', 'data': formatted_jobs})}\n\n"

                # Step 5: Generate job summary
                yield f"data: {json.dumps({'step': 'generating_summary', 'message': 'Analyzing job requirements...'})}\n\n"
                job_descriptions = top_jobs.head(12)['description'].tolist()
                job_summary = generate_job_summary(job_descriptions)
                yield f"data: {json.dumps({'step': 'summary_generated', 'data': job_summary})}\n\n"

                # Step 6: Analyze skill gaps
                yield f"data: {json.dumps({'step': 'analyzing_gaps', 'message': 'Analyzing skill gaps...'})}\n\n"
                job_market_skills = extract_skills_from_summary(job_summary)
                missing_skills = compare_skills(curriculum_skills, job_market_skills)
                yield f"data: {json.dumps({'step': 'gaps_analyzed', 'data': {'missing_skills': missing_skills, 'job_market_skills': job_market_skills}})}\n\n"

                # Step 7: Generate projects
                yield f"data: {json.dumps({'step': 'generating_projects', 'message': 'Generating project recommendations...'})}\n\n"
                major_project = generate_job_based_project(job_summary)
                # Convert markdown table to point-wise format
                major_project_points = markdown_table_to_points(major_project)
                yield f"data: {json.dumps({'step': 'major_project_generated', 'data': major_project_points})}\n\n"
                mini_projects = generate_job_based_mini_projects(job_summary)
                yield f"data: {json.dumps({'step': 'mini_projects_generated', 'data': mini_projects})}\n\n"

                # Step 8: Complete
                yield f"data: {json.dumps({'step': 'complete', 'message': 'Analysis complete!'})}\n\n"

            except Exception as e:
                logger.error(f"Error in complete analysis: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Accept'
        return response

    def post(self, request, *args, **kwargs):
        serializer = CurriculumAnalysisSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        curriculum_text = serializer.validated_data['curriculum_text']
        return Response({"message": "Analysis started"}, status=status.HTTP_200_OK)

    def options(self, request, *args, **kwargs):
        response = Response()
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, Accept"
        return response

@csrf_exempt
def complete_analysis_dispatch(request: HttpRequest, *args, **kwargs):
    if request.method == "GET":
        view = CompleteAnalysisStreamView.as_view()
    else:
        view = CompleteAnalysisView.as_view()
    return view(request, *args, **kwargs)

def markdown_table_to_points(md_table: str) -> str:
    """
    Convert a markdown table string to a point-wise project list.
    """
    lines = [line.strip() for line in md_table.strip().splitlines() if line.strip()]
    if len(lines) < 3:
        return md_table  # Not a table, return as is

    headers = [h.strip() for h in lines[0].split('|')[1:-1]]
    projects = []
    for row in lines[2:]:
        cols = [c.strip() for c in row.split('|')[1:-1]]
        if len(cols) != len(headers):
            continue
        project = {headers[i]: cols[i] for i in range(len(headers))}
        projects.append(project)

    # Format as point-wise
    result = []
    for idx, proj in enumerate(projects, 1):
        result.append(f"**Project {idx}: {proj.get('Project Title', '')}**")
        for key, val in proj.items():
            if key != 'Project Title':
                result.append(f"- **{key}:** {val}")
        result.append("")  # Blank line between projects
    return "\n".join(result)
