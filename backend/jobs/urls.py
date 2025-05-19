from django.urls import path
from .views import (
    CurriculumAnalysisView,
    JobAnalysisView,
    SkillComparisonView,
    ProjectGenerationView,
    CompleteAnalysisView,
    CompleteAnalysisStreamView,
    complete_analysis_dispatch,  # Add this import
)

urlpatterns = [
    path('analyze-curriculum/', CurriculumAnalysisView.as_view(), name='analyze-curriculum'),
    path('analyze-jobs/', JobAnalysisView.as_view(), name='analyze-jobs'),
    path('generate-projects/', ProjectGenerationView.as_view(), name='generate-projects'),
    path('compare-skills/', SkillComparisonView.as_view(), name='compare-skills'),
    path('complete-analysis/', complete_analysis_dispatch, name='complete-analysis'),  # Use dispatcher
]