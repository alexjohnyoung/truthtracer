// Results Renderer Module
const ResultsRenderer = {
    // Main display function
    displayResults(data) {
        const resultsSection = document.getElementById('resultsSection');
        resultsSection.classList.remove('d-none');
        
        // Add class to body to shrink log container
        document.body.classList.add('results-displayed');
        
        const resultData = data.result || {};
        const articleData = resultData.article || {};
        
        this.renderArticleInfo(articleData, data.url);
        this.renderReliabilityAnalysis(resultData);
        this.renderReferenceArticles(resultData);
        this.renderSkippedReferences(resultData);
    },
    
    // Article information
    renderArticleInfo(articleData, url) {
        // Set article metadata
        document.getElementById('articleTitle').textContent = articleData.headline || articleData.title || 'N/A';
        document.getElementById('articleAuthor').textContent = articleData.author || 'N/A';
        document.getElementById('articleSummary').textContent = articleData.summary || 'No summary available.';
        document.getElementById('articleDate').textContent = articleData.publishDate || articleData.date || 'N/A';
        
        // Extract domain from URL
        let domain = 'N/A';
        try {
            if (url) {
                const urlObj = new URL(url);
                domain = urlObj.hostname.replace('www.', '');
            }
        } catch (e) {}
        document.getElementById('articleWebsite').textContent = domain;
        
        // Render claims
        const claimsList = document.getElementById('articleClaimsList');
        claimsList.innerHTML = '';
        
        if (articleData.claims && articleData.claims.length > 0) {
            articleData.claims.forEach(claim => {
                if (!claim) return;
                
                const claimText = typeof claim === 'object' ? claim.text : claim;
                if (claimText) {
                    const li = document.createElement('li');
                    li.className = 'mb-1';
                    li.innerHTML = `
                        <div class="d-flex">
                            <div class="me-2"><i class="bi bi-check-circle-fill"></i></div>
                            <div>${claimText}</div>
                        </div>
                    `;
                    claimsList.appendChild(li);
                }
            });
        } else {
            claimsList.innerHTML = '<p class="text-muted small">No claims identified.</p>';
        }
    },
    
    // Reliability analysis
    renderReliabilityAnalysis(resultData) {
        const container = document.getElementById('misleadingAnalysisContent');
        container.innerHTML = '';
        
        const crossRefData = resultData.cross_reference || null;
        if (!crossRefData || !crossRefData.explanation) {
            container.innerHTML = `
                <div class="card-header bg-dark border-secondary">
                    <h5 class="mb-0">Reliability</h5>
                </div>
                <div class="card-body">
                    <div class="alert alert-warning p-2">
                        <p class="mb-0 small">Reliability assessment is not available.</p>
                    </div>
                </div>
            `;
            return;
        }
        
        // Header
        const isMisleading = crossRefData.isMisleading || false;
        const themeClass = isMisleading ? 'bg-danger' : 'bg-success';
        const themeIcon = isMisleading ? 'bi-exclamation-triangle-fill' : 'bi-shield-check';
        const themeText = isMisleading ? 'POTENTIALLY MISLEADING' : 'LOOKS RELIABLE';
        
        // Create HTML
        container.innerHTML = `
            <div class="card-header bg-dark border-secondary">
                <h5 class="mb-0"><i class="bi ${themeIcon} me-2"></i> Reliability</h5>
            </div>
            <div class="card-body p-3">
                <div class="alert ${themeClass} text-center mb-3">
                    <h4 class="alert-heading mb-0 text-black">${themeText}</h4>
                </div>
                
                ${crossRefData.explanation ? `
                <div class="bg-dark p-3 rounded border border-secondary mb-3">
                    <h6 class="border-bottom pb-1 mb-2 text-info fw-bold">Analysis</h6>
                    <p class="mb-0">${crossRefData.explanation}</p>
                </div>
                ` : ''}
                
                ${crossRefData.confidence ? `                
                <div class="text-center mt-3">
                    <span class="badge bg-info px-2 py-1">
                        Confidence: ${Math.round(crossRefData.confidence * 100)}%
                    </span>
                </div>
                ` : ''}
            </div>
        `;
    },
    
    // Reference articles
    renderReferenceArticles(resultData) {
        const container = document.getElementById('referenceArticlesContent');
        container.innerHTML = '';
        
        // Add header
        container.innerHTML = `
            <div class="card-header bg-dark border-secondary">
                <h5 class="mb-0"><i class="bi bi-journals me-2"></i> Reference Articles</h5>
            </div>
            <div class="card-body p-3" id="referencesBody">
                <div class="alert alert-warning p-2">
                    <p class="mb-0 small">No reference articles available.</p>
                </div>
            </div>
        `;
        
        // Check if we have references
        const references = resultData.reference_processing?.successful || [];
        if (!references.length) return;
        
        // Create reference content
        const referencesBody = document.getElementById('referencesBody');
        referencesBody.innerHTML = '<div id="referencesList"></div>';
        
        const referencesList = document.getElementById('referencesList');
        references.forEach(ref => {
            if (!ref || !ref.url) return;
            
            const article = document.createElement('div');
            article.className = 'reference-article mb-3 pb-2 border-bottom';
            
            // Extract data
            const title = ref.title || ref.headline || 'Untitled Reference';
            const source = ref.source || new URL(ref.url).hostname.replace('www.', '');
            const author = ref.author || 'Unknown author';
            const publishDate = ref.publishDate || 'Date unknown';
            // Check for summary in both direct property and nested inside analysis object
            const summary = ref.summary || (ref.analysis && ref.analysis.summary) || ref.snippet || 'No summary available';
            
            article.innerHTML = `
                <div class="d-flex justify-content-between">
                    <div class="fw-bold">${title}</div>
                    <a href="${ref.url}" target="_blank" class="btn btn-sm btn-outline-info">
                        <i class="bi bi-box-arrow-up-right"></i>
                    </a>
                </div>
                <div class="small text-muted mb-1">
                    ${source} • ${publishDate} • ${author}
                </div>
                <div class="small">${summary}</div>
            `;
            
            referencesList.appendChild(article);
        });
    },
    
    // Skipped references
    renderSkippedReferences(resultData) {
        const skippedSection = document.getElementById('skippedReferences');
        const skippedContent = document.getElementById('skippedReferencesContent');
        
        // Reset content
        skippedContent.innerHTML = '';
        
        // Get skipped references
        const skipped = resultData.reference_processing?.skipped || [];
        
        if (skipped.length > 0) {
            skippedSection.classList.remove('d-none');
            
            skipped.forEach(item => {
                const div = document.createElement('div');
                div.className = 'mb-2';
                div.innerHTML = `
                    <div class="d-flex justify-content-between">
                        <div>
                            <strong class="small">${item.title || 'Unknown Source'}</strong>
                            <div class="small text-muted">${item.url || ''}</div>
                        </div>
                        <span class="badge bg-danger">${item.reason || 'Error'}</span>
                    </div>
                `;
                skippedContent.appendChild(div);
            });
        } else {
            skippedSection.classList.add('d-none');
        }
    }
};

export default ResultsRenderer; 
