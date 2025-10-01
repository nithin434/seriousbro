function displayTechStack(techStack) {
    if (!techStack) return '';

    return `
        <div class="space-y-6">
            ${Object.entries(techStack).map(([category, items]) => `
                <div>
                    <h4 class="font-medium text-gray-700 mb-2">${category.replace('_', ' ').toUpperCase()}</h4>
                    <div class="flex flex-wrap gap-2">
                        ${Array.isArray(items) ? items.map(item => `
                            <span class="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                                ${item}
                            </span>
                        `).join('') : ''}
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}