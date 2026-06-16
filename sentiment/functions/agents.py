from finrobot.agents.workflow import FinRobot
from .utils.read_and_clean import read_file_content

def create_scorer_agent(prompt_path, schema_path, llm_config):
    """Instantiates and returns the Sentiment Scorer agent."""
    schema_str = read_file_content(schema_path)
    scorer_prompt_template = read_file_content(prompt_path)
    
    scorer_profile = scorer_prompt_template.format(
        SCHEMA=schema_str,
        EXAMPLES="Use the matching 'calibration_examples' list provided inline inside the user message for each article."
    )
    
    return FinRobot(
        agent_config={
            "name": "Sentiment_Scorer",
            "description": "Scoration specialist agent.",
            "profile": scorer_profile,
            "toolkits": []
        },
        llm_config=llm_config
    )

def create_cio_agent(prompt_path, schema_path, output_schema_path, scored_articles_path, llm_config):
    """Instantiates and returns the Senior Sentiment Analyst (CIO) agent."""
    cio_prompt_template = read_file_content(prompt_path)
    schema_str = read_file_content(schema_path)
    output_str = read_file_content(output_schema_path)
    scored_articles_str = read_file_content(scored_articles_path)
    
    cio_profile = cio_prompt_template.format(
        SCHEMA=schema_str,
        EXAMPLES=scored_articles_str,
        OUTPUT=output_str
    )
    
    return FinRobot(
        agent_config={
            "name": "Senior_Sentiment_Analyst",
            "description": "Consolidation and aggregation agent.",
            "profile": cio_profile,
            "toolkits": []
        },
        llm_config=llm_config
    )

def create_forexfactory_agent(prompt_path, schema_path, example_path, llm_config):
    """Instantiates and returns the ForexFactory Scraper agent."""
    prompt_template = read_file_content(prompt_path)
    schema_str = read_file_content(schema_path)
    example_str = read_file_content(example_path)
    
    profile = prompt_template.format(
        SCHEMA=schema_str,
        EXAMPLES=example_str
    )
    
    return FinRobot(
        agent_config={
            "name": "ForexFactory_Scraper_Agent",
            "description": "Specialist scraper that retrieves real-time calendar values for specific macroeconomic events.",
            "profile": profile,
            "toolkits": []
        },
        llm_config=llm_config
    )

def create_alphavantage_agent(prompt_path, schema_path, example_path, llm_config):
    """Instantiates and returns the Alpha Vantage agent."""
    prompt_template = read_file_content(prompt_path)
    schema_str = read_file_content(schema_path)
    example_str = read_file_content(example_path)
    
    profile = prompt_template.format(
        SCHEMA=schema_str,
        EXAMPLES=example_str
    )
    
    return FinRobot(
        agent_config={
            "name": "AlphaVantage_Agent",
            "description": "Specialist in historical baselines and rolling standard deviation calculations.",
            "profile": profile,
            "toolkits": []
        },
        llm_config=llm_config
    )

def create_macro_cio_agent(prompt_path, schema_path, example_path, llm_config):
    """Instantiates and returns the Chief Macro Economist agent."""
    prompt_template = read_file_content(prompt_path)
    schema_str = read_file_content(schema_path)
    example_str = read_file_content(example_path)
    
    profile = prompt_template.format(
        SCHEMA=schema_str,
        EXAMPLES=example_str
    )
    
    return FinRobot(
        agent_config={
            "name": "Chief_Macro_Economist",
            "description": "Executive macro analyst that calculates final macro surprise scores and compiles JSON reports.",
            "profile": profile,
            "toolkits": []
        },
        llm_config=llm_config
    )
