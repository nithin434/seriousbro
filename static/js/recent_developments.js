function displayRecentDevelopments(developments) {
    if (!developments || !Array.isArray(developments)) return '';

    return `
        <div class="space-y-4">
            ${developments.map(dev => `
                <div class="bg-white rounded-lg border p-4">
                    <h4 class="font-medium text-lg text-gray-800">${dev.title}</h4>
                    <p class="text-gray-600 mt-1">${dev.description}</p>
                    <div class="flex justify-between items-center mt-2">
                        <span class="text-sm text-gray-500">${dev.date}</span>
                        <span class="text-sm text-blue-600">${dev.impact}</span>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}