document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('uploadForm');
    if (!form) return;
    
    const statusDiv = document.getElementById('status');
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Show initial loading state
        statusDiv.innerHTML = `
            <div class="bg-blue-100 text-blue-700 p-4 rounded">
                <div class="flex items-center">
                    <svg class="animate-spin h-5 w-5 mr-3" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
                    </svg>
                    <span>Uploading resume...</span>
                </div>
            </div>
        `;
        statusDiv.classList.remove('hidden');
        
        const formData = new FormData(form);
        
        try {
            console.log("Sending upload request...");
            const response = await fetch('/api/resume/upload', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            console.log("Upload response:", result);
            
            if (result.success) {
                // Show processing status
                statusDiv.innerHTML = `
                    <div class="bg-blue-100 text-blue-700 p-4 rounded">
                        <div class="flex items-center">
                            <svg class="animate-spin h-5 w-5 mr-3" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
                            </svg>
                            <span>Processing resume...</span>
                        </div>
                    </div>
                `;

                // Redirect to dashboard
                if (result.status === 'complete') {
                    console.log("Processing complete, redirecting to:", result.redirect_url);
                    window.location.href = result.redirect_url;
                }
            } else {
                throw new Error(result.error || "Upload failed");
            }
        } catch (error) {
            console.error("Upload error:", error);
            statusDiv.innerHTML = `
                <div class="bg-red-100 text-red-700 p-4 rounded">
                    <div class="flex items-center">
                        <svg class="h-5 w-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
                        </svg>
                        <span>Error: ${error.message}</span>
                    </div>
                </div>
            `;
        }
    });
});