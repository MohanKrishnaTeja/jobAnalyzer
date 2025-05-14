from django.urls import path
from .views import (
    CurriculumAnalysisView,
    JobAnalysisView,
    SkillComparisonView,
    ProjectGenerationView
)

urlpatterns = [
    path('analyze-curriculum/', CurriculumAnalysisView.as_view(), name='analyze-curriculum'),
    path('analyze-jobs/', JobAnalysisView.as_view(), name='analyze-jobs'),
    path('generate-projects/', ProjectGenerationView.as_view(), name='generate-projects'),
    path('compare-skills/', SkillComparisonView.as_view(), name='compare-skills'),
] 