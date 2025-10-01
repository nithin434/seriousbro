const LinkedInSessionCreator = require('./manual_session_creator');
const fs = require('fs');
const path = require('path');

class LinkedInScraper {
    constructor() {
        this.sessionCreator = new LinkedInSessionCreator();
        this.page = null;
        this.outputDir = path.join(__dirname, 'scraped_data');
        this.ensureOutputDir();
    }

    ensureOutputDir() {
        if (!fs.existsSync(this.outputDir)) {
            fs.mkdirSync(this.outputDir, { recursive: true });
            console.log('📁 Created output directory:', this.outputDir);
        }
    }

    async initialize() {
        await this.sessionCreator.createSession();
        this.page = this.sessionCreator.getPage();
        return this.page;
    }

    async navigateToMyProfile() {
        try {
            console.log('🏠 Navigating to your profile...');
            await this.page.goto('https://www.linkedin.com/in/me/', { waitUntil: 'networkidle' });
            await this.page.waitForTimeout(2000);
            console.log('✅ Successfully navigated to your profile');
            return true;
        } catch (error) {
            console.error('❌ Error navigating to profile:', error.message);
            return false;
        }
    }

    async scrapeProfile(profileUrl) {
        try {
            console.log(`🔍 Scraping profile: ${profileUrl}`);
            await this.page.goto(profileUrl, { waitUntil: 'networkidle', timeout: 30000 });
            
            // Wait for main content to load
            await this.page.waitForSelector('main', { timeout: 15000 });
            await this.page.waitForTimeout(3000); // Additional wait for dynamic content
            
            const profileData = await this.page.evaluate(() => {
                const data = {};
                
                // Helper function to safely get text content
                const getText = (selector) => {
                    const element = document.querySelector(selector);
                    return element ? element.textContent.trim() : 'N/A';
                };
                
                // Name - multiple selectors
                data.name = getText('h1.text-heading-xlarge') || 
                           getText('.text-heading-xlarge') || 
                           getText('.pv-text-details__left-panel h1') || 'N/A';
                
                // Headline - multiple selectors
                data.headline = getText('.text-body-medium.break-words') || 
                               getText('.pv-text-details__left-panel .text-body-medium') ||
                               getText('.pv-top-card--headline') || 'N/A';
                
                // Location - multiple selectors
                data.location = getText('.text-body-small.inline.t-black--light.break-words') ||
                               getText('.pv-text-details__left-panel .text-body-small') ||
                               getText('.pv-top-card--location') || 'N/A';
                
                // Connection count
                data.connections = getText('.pv-top-card--connections') || 'N/A';
                
                // About section - multiple selectors
                data.about = getText('#about ~ * .inline-show-more-text') ||
                            getText('.pv-about__summary-text') ||
                            getText('[data-generated-suggestion-target]') || 'N/A';
                
                // Experience section
                const experienceElements = document.querySelectorAll('#experience ~ * .pvs-list__item');
                data.experience = [];
                experienceElements.forEach((exp, index) => {
                    if (index < 5) { // Limit to first 5 experiences
                        const title = exp.querySelector('.mr1.hoverable-link-text span[aria-hidden="true"]')?.textContent?.trim();
                        const company = exp.querySelector('.pv-entity__secondary-title')?.textContent?.trim();
                        if (title) {
                            data.experience.push({
                                title: title || 'N/A',
                                company: company || 'N/A'
                            });
                        }
                    }
                });
                
                // Education section
                const educationElements = document.querySelectorAll('#education ~ * .pvs-list__item');
                data.education = [];
                educationElements.forEach((edu, index) => {
                    if (index < 3) { // Limit to first 3 education entries
                        const school = edu.querySelector('.mr1.hoverable-link-text span[aria-hidden="true"]')?.textContent?.trim();
                        const degree = edu.querySelector('.pv-entity__degree-name')?.textContent?.trim();
                        if (school) {
                            data.education.push({
                                school: school || 'N/A',
                                degree: degree || 'N/A'
                            });
                        }
                    }
                });
                
                // Skills section
                const skillElements = document.querySelectorAll('#skills ~ * .pvs-list__item span[aria-hidden="true"]');
                data.skills = [];
                skillElements.forEach((skill, index) => {
                    if (index < 10) { // Limit to first 10 skills
                        const skillText = skill.textContent?.trim();
                        if (skillText && !data.skills.includes(skillText)) {
                            data.skills.push(skillText);
                        }
                    }
                });
                
                return data;
            });
            
            console.log('✅ Profile data scraped successfully');
            
            // Save to file
            await this.saveProfileData(profileData, profileUrl);
            
            return profileData;
            
        } catch (error) {
            console.error('❌ Error scraping profile:', error.message);
            return null;
        }
    }

    async saveProfileData(profileData, profileUrl) {
        try {
            const filename = `profile_${profileData.name.replace(/[^a-zA-Z0-9]/g, '_')}_${Date.now()}.json`;
            const filepath = path.join(this.outputDir, filename);
            
            const dataToSave = {
                ...profileData,
                scrapedAt: new Date().toISOString(),
                profileUrl: profileUrl
            };
            
            fs.writeFileSync(filepath, JSON.stringify(dataToSave, null, 2));
            console.log(`💾 Profile data saved to: ${filename}`);
        } catch (error) {
            console.error('❌ Error saving profile data:', error.message);
        }
    }

    async searchAndScrape(searchQuery, maxResults = 10) {
        try {
            console.log(`🔍 Searching for: ${searchQuery}`);
            
            // Navigate to people search
            const searchUrl = `https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(searchQuery)}`;
            await this.page.goto(searchUrl, { waitUntil: 'networkidle', timeout: 30000 });
            
            // Wait for search results
            await this.page.waitForSelector('.search-results-container', { timeout: 15000 });
            await this.page.waitForTimeout(3000); // Wait for dynamic loading
            
            const profiles = await this.page.evaluate((maxResults) => {
                const profileElements = document.querySelectorAll('.search-results__list .search-result');
                const profiles = [];
                
                for (let i = 0; i < Math.min(profileElements.length, maxResults); i++) {
                    const element = profileElements[i];
                    
                    // Multiple selectors for name
                    const nameElement = element.querySelector('.entity-result__title-text a span[aria-hidden="true"]') ||
                                       element.querySelector('.entity-result__title-text a span') ||
                                       element.querySelector('.app-aware-link span[aria-hidden="true"]');
                    
                    const headlineElement = element.querySelector('.entity-result__primary-subtitle');
                    const locationElement = element.querySelector('.entity-result__secondary-subtitle');
                    const linkElement = element.querySelector('.entity-result__title-text a') ||
                                       element.querySelector('.app-aware-link');
                    
                    if (nameElement && linkElement) {
                        profiles.push({
                            name: nameElement.textContent.trim(),
                            headline: headlineElement ? headlineElement.textContent.trim() : 'N/A',
                            location: locationElement ? locationElement.textContent.trim() : 'N/A',
                            profileUrl: linkElement.href.split('?')[0] // Remove query parameters
                        });
                    }
                }
                
                return profiles;
            }, maxResults);
            
            console.log(`✅ Found ${profiles.length} profiles`);
            
            // Save search results
            await this.saveSearchResults(searchQuery, profiles);
            
            return profiles;
            
        } catch (error) {
            console.error('❌ Error searching profiles:', error.message);
            return [];
        }
    }

    async saveSearchResults(searchQuery, profiles) {
        try {
            const filename = `search_${searchQuery.replace(/[^a-zA-Z0-9]/g, '_')}_${Date.now()}.json`;
            const filepath = path.join(this.outputDir, filename);
            
            const dataToSave = {
                searchQuery: searchQuery,
                searchedAt: new Date().toISOString(),
                totalResults: profiles.length,
                profiles: profiles
            };
            
            fs.writeFileSync(filepath, JSON.stringify(dataToSave, null, 2));
            console.log(`💾 Search results saved to: ${filename}`);
        } catch (error) {
            console.error('❌ Error saving search results:', error.message);
        }
    }

    async bulkScrapeProfiles(profileUrls, delay = 5000) {
        const results = [];
        
        for (let i = 0; i < profileUrls.length; i++) {
            console.log(`\n📋 Scraping profile ${i + 1}/${profileUrls.length}`);
            
            const profileData = await this.scrapeProfile(profileUrls[i]);
            if (profileData) {
                results.push(profileData);
            }
            
            // Add delay between requests to avoid rate limiting
            if (i < profileUrls.length - 1) {
                console.log(`⏳ Waiting ${delay/1000} seconds before next profile...`);
                await this.page.waitForTimeout(delay);
            }
        }
        
        return results;
    }    async scrapeProfileDirect(profileUrl) {
        try {
            console.log(`🔍 Scraping profile: ${profileUrl}`);
            await this.page.goto(profileUrl, { waitUntil: 'networkidle', timeout: 30000 });
            
            // Wait for main content to load
            await this.page.waitForSelector('main', { timeout: 15000 });
            await this.page.waitForTimeout(3000); // Additional wait for dynamic content
            
            const profileData = await this.page.evaluate(() => {
                const data = {};
                
                // Get the entire page text content
                data.rawPageText = document.body.innerText || 'N/A';
                
                // Get the HTML content of main sections
                const mainElement = document.querySelector('main');
                data.rawMainHTML = mainElement ? mainElement.innerHTML : 'N/A';
                
                // Get all visible text from the page
                data.allVisibleText = Array.from(document.querySelectorAll('*'))
                    .map(el => el.innerText)
                    .filter(text => text && text.trim().length > 0)
                    .join('\n');
                
                // Get page title
                data.pageTitle = document.title || 'N/A';
                
                // Get URL
                data.currentUrl = window.location.href || 'N/A';
                
                // Get all text content by sections
                const sections = {};
                document.querySelectorAll('section, div[class*="section"], div[id]').forEach((section, index) => {
                    const sectionText = section.innerText?.trim();
                    const sectionId = section.id || section.className || `section_${index}`;
                    if (sectionText && sectionText.length > 10) {
                        sections[sectionId] = sectionText;
                    }
                });
                data.sectionTexts = sections;
                
                return data;
            });
            
            console.log('✅ LinkedIn profile raw data scraped successfully');
            return profileData;
            
        } catch (error) {
            console.error('❌ Error scraping profile:', error.message);
            return null;
        }
    }    async scrapeGitHubProfile(githubUrl) {
        try {
            console.log(`🔍 Scraping GitHub profile: ${githubUrl}`);
            await this.page.goto(githubUrl, { waitUntil: 'networkidle', timeout: 30000 });
            await this.page.waitForTimeout(3000);
            
            const githubData = await this.page.evaluate(() => {
                const data = {};
                
                // Get the entire page text content
                data.rawPageText = document.body.innerText || 'N/A';
                
                // Get the HTML content of main sections
                data.rawMainHTML = document.body.innerHTML || 'N/A';
                
                // Get all visible text from the page
                data.allVisibleText = Array.from(document.querySelectorAll('*'))
                    .map(el => el.innerText)
                    .filter(text => text && text.trim().length > 0)
                    .join('\n');
                
                // Get page title
                data.pageTitle = document.title || 'N/A';
                
                // Get URL
                data.currentUrl = window.location.href || 'N/A';
                
                // Get all text content by sections
                const sections = {};
                document.querySelectorAll('section, div[class*="section"], div[id], article').forEach((section, index) => {
                    const sectionText = section.innerText?.trim();
                    const sectionId = section.id || section.className || `section_${index}`;
                    if (sectionText && sectionText.length > 10) {
                        sections[sectionId] = sectionText;
                    }
                });
                data.sectionTexts = sections;
                
                // Also get specific GitHub data if available
                const getText = (selector) => {
                    const element = document.querySelector(selector);
                    return element ? element.textContent.trim() : 'N/A';
                };
                
                data.extractedData = {
                    name: getText('.p-name') || getText('h1.vcard-names span') || 'N/A',
                    username: getText('.p-nickname') || 'N/A',
                    bio: getText('.p-note.user-profile-bio') || 'N/A',
                    location: getText('[itemprop="homeLocation"]') || 'N/A',
                    company: getText('[itemprop="worksFor"]') || 'N/A',
                    followers: getText('a[href$="followers"] span') || 'N/A',
                    following: getText('a[href$="following"] span') || 'N/A',
                    repositories: getText('a[href$="repositories"] span') || 'N/A'
                };
                
                return data;
            });
            
            console.log('✅ GitHub profile raw data scraped successfully');
            return githubData;
            
        } catch (error) {
            console.error('❌ Error scraping GitHub profile:', error.message);
            return null;
        }
    }    async scrapeGitHubRepos(reposUrl) {
        try {
            console.log(`🔍 Scraping GitHub repositories: ${reposUrl}`);
            await this.page.goto(reposUrl, { waitUntil: 'networkidle', timeout: 30000 });
            await this.page.waitForTimeout(3000);
            
            const reposData = await this.page.evaluate(() => {
                const data = {};
                
                // Get the entire page text content
                data.rawPageText = document.body.innerText || 'N/A';
                
                // Get the HTML content of main sections
                data.rawMainHTML = document.body.innerHTML || 'N/A';
                
                // Get all visible text from the page
                data.allVisibleText = Array.from(document.querySelectorAll('*'))
                    .map(el => el.innerText)
                    .filter(text => text && text.trim().length > 0)
                    .join('\n');
                
                // Get page title
                data.pageTitle = document.title || 'N/A';
                
                // Get URL
                data.currentUrl = window.location.href || 'N/A';
                
                // Also extract specific repository data if available
                const repos = [];
                const repoElements = document.querySelectorAll('#user-repositories-list [data-testid="repositories-search-listbox"] li');
                
                repoElements.forEach((repo, index) => {
                    if (index < 10) { // Limit to first 10 repos
                        const nameElement = repo.querySelector('h3 a');
                        const descElement = repo.querySelector('p');
                        const langElement = repo.querySelector('[itemprop="programmingLanguage"]');
                        const starsElement = repo.querySelector('a[href$="/stargazers"]');
                        
                        if (nameElement) {
                            repos.push({
                                name: nameElement.textContent.trim(),
                                description: descElement ? descElement.textContent.trim() : 'N/A',
                                language: langElement ? langElement.textContent.trim() : 'N/A',
                                stars: starsElement ? starsElement.textContent.trim() : '0',
                                url: nameElement.href
                            });
                        }
                    }
                });
                
                data.extractedRepos = repos;
                
                return data;
            });
            
            console.log('✅ GitHub repositories raw data scraped successfully');
            return reposData;
            
        } catch (error) {
            console.error('❌ Error scraping GitHub repositories:', error.message);
            return null;
        }
    }

    async close() {
        await this.sessionCreator.saveSession();
        if (this.sessionCreator.browser) {
            await this.sessionCreator.browser.close();
        }
    }
}

module.exports = LinkedInScraper;

// Direct scraping function for Python integration
async function scrapeDirectly(urls) {
    const scraper = new LinkedInScraper();
    
    try {
        console.log('🔄 Initializing scraper...');
        await scraper.initialize();
        console.log('✅ Scraper initialized successfully');
        
        const results = {};
        
        for (const [type, url] of Object.entries(urls)) {
            if (url && url !== 'N/A') {
                console.log(`\n🔍 Scraping ${type}: ${url}`);
                
                if (type === 'linkedin') {
                    results[type] = await scraper.scrapeProfileDirect(url);
                } else if (type === 'github') {
                    results[type] = await scraper.scrapeGitHubProfile(url);
                } else if (type === 'repos') {
                    results[type] = await scraper.scrapeGitHubRepos(url);
                }
                
                console.log(`✅ ${type} scraping completed`);
                await scraper.page.waitForTimeout(2000); // Small delay between requests
            }
        }
        
        console.log('\n📊 All scraping completed!');
        console.log('='.repeat(50));
        console.log(JSON.stringify(results, null, 2));
        console.log('='.repeat(50));
        
        // Close browser properly
        console.log('🔒 Closing browser...');
        await scraper.close();
        
        // Exit the process to ensure it doesn't hang
        process.exit(0);
        
    } catch (error) {
        console.error('❌ Error in direct scraping:', error.message);
        try {
            await scraper.close();
        } catch (closeError) {
            console.error('❌ Error closing scraper:', closeError.message);
        }
        process.exit(1);
    }
}

// Check if called directly with arguments
if (require.main === module && process.argv.length > 2) {
    const urls = {};
    
    // Parse command line arguments
    process.argv.slice(2).forEach(arg => {
        if (arg.startsWith('github:')) {
            urls.github = arg.replace('github:', '');
        } else if (arg.startsWith('repos:')) {
            urls.repos = arg.replace('repos:', '');
        } else if (arg.startsWith('linkedin:')) {
            urls.linkedin = arg.replace('linkedin:', '');
        }
    });
    
    console.log('🚀 Starting direct scraping with URLs:', urls);
    scrapeDirectly(urls);
}
