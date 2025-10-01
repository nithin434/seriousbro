function displayGuide(guide) {
    try {
        // Company Research
        displayCompanyResearch(guide.company_research);
        
        // Interview Rounds
        if (guide.interview_preparation?.rounds) {
            displayInterviewRounds(guide.interview_preparation.rounds);
        }
        
        // Timeline & Resources
        displayPreparationTimeline(guide.interview_preparation?.recommended_timeline || []);
        displayLearningResources(guide.interview_preparation?.resources || {});
        
        // Show sections if they exist
        const sections = {
            'technicalPrep': guide.technical_preparation,
            'behavioralPrep': guide.behavioral_questions,
            'companyQuestions': guide.company_questions,
            'prepTips': guide.preparation_tips
        };

        Object.entries(sections).forEach(([elementId, data]) => {
            const element = document.getElementById(elementId);
            if (element && data) {
                element.innerHTML = getSectionContent(elementId, data);
                element.closest('.bg-white')?.classList.remove('hidden');
            }
        });

        document.getElementById('guideContent').classList.remove('hidden');
        
    } catch (error) {
        console.error('Error displaying guide:', error);
        document.getElementById('errorMessage').textContent = 'Error displaying interview guide';
        document.getElementById('errorMessage').classList.remove('hidden');
    }
}