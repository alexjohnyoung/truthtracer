class ArticleAnalysis {
  claims string[] @description("Main statements from the text")
  summary string @description("Short neutral summary")
}


class MisleadingAnalysis {
  isMisleading bool @description("Clear false information from main article found")
  confidence float @description("Confidence score between 0 and 1")
  reasons string[] @description("List of main issues found")
  explanation string @description("Plain English summary of problems")
}

class CleanedArticle {
  text string @description("Cleaned article text")
}

function ExtractArticleInfo(articleText: string) -> ArticleAnalysis {
    client "Gemma"
    prompt #"
    Extract key information from this news article. You must return EXACTLY this JSON format with no deviations:
    {
      "claims": [
        "First key claim from the article",
        "Second key claim from the article"
      ],
      "summary": "A brief factual summary of the main points"
    }

    CRITICAL RULES:
    1. All fields must be present
    2. Do not add any extra fields
    3. Do not add any comments
    4. Include at least 3-5 key claims from the article

    Article:
    {{articleText}}
    "#
}
function AnalyseMisleadingContent(
  article: ArticleAnalysis, 
  referenceArticles: ArticleAnalysis[],
  mainTitle: string,
  referenceTitles: string[]
) -> MisleadingAnalysis {
  client "Gemma"
  prompt #"
    Compare the main article with reference articles and determine if it's misleading.
    
    Main article:
    Title: {{ mainTitle }}
    Claims: 
    {% for claim in article.claims %}
    - {{ claim }}
    {% endfor %}
    Summary: {{ article.summary }}

    Reference articles:
    {% for ref in referenceArticles %}
    Title: {{ referenceTitles[loop.index-1] }}
    Claims:
    {% for claim in ref.claims %}
    - {{ claim }}
    {% endfor %}
    Summary: {{ ref.summary }}
    {% endfor %}

    An article is misleading if claims are contradicted by multiple sources, important context is missing, or it contains significant factual errors.

    Return ONLY this JSON:
    ```json
    {
      "isMisleading": true/false,
      "confidence": 0.0-1.0,
      "reasons": ["Reason 1", "Reason 2"],
      "explanation": "Brief explanation of the assessment"
    }
    ```
  "#
}

function CleanArticleText(articleText: string) -> CleanedArticle {
  client "Gemma"
  prompt #"
    You are an AI that VERY AGGRESSIVELY cleans news articles by removing ALL noise.

    Clean this article by:
    1. REMOVE ALL navigation menus, ads, footers, share buttons, newsletters, cookies, sidebars
    2. KEEP ONLY THE FULL ARTICLE TEXT

    Article to clean:
    {{articleText}}

    Return ONLY this JSON format:
    {
      "text": "cleaned article text"
    }
  "#
}
