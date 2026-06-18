from finrobot.agents.workflow import FinRobot
from .utils.common.read_and_clean import read_file_content

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

def create_decomposition_agent(prompt_path, schema_path, example_path, llm_config):
    """Instantiates and returns the Decomposition Worker agent."""
    prompt_template = read_file_content(prompt_path)
    schema_str = read_file_content(schema_path)
    example_str = read_file_content(example_path)
    
    profile = prompt_template.format(
        SCHEMA=schema_str,
        EXAMPLES=example_str
    )
    
    return FinRobot(
        agent_config={
            "name": "Decomposition_Worker",
            "description": "Decomposition worker that decomposes the ETF into its constituent tickers and weights.",
            "profile": profile,
            "toolkits": []
        },
        llm_config=llm_config
    )

def create_textual_inertia_agent(prompt_path, llm_config):
    """Instantiates and returns the Textual Inertia (\"Lazy Prices\") Agent."""
    profile = read_file_content(prompt_path)
    return FinRobot(
        agent_config={
            "name": "Textual_Inertia_Agent",
            "description": "Tracks text deviations between consecutive annual corporate filings (10-K).",
            "profile": profile,
            "toolkits": []
        },
        llm_config=llm_config
    )

def create_tension_extractor_agent(prompt_path, llm_config):
    """Instantiates and returns the Analyst Q&A Tension Extractor Agent."""
    profile = read_file_content(prompt_path)
    return FinRobot(
        agent_config={
            "name": "Tension_Extractor_Agent",
            "description": "Analyzes earnings call transcripts to trace signs of corporate tension and defensiveness.",
            "profile": profile,
            "toolkits": []
        },
        llm_config=llm_config
    )

def create_scribe_agent(prompt_path, llm_config):
    """Instantiates and returns the Thesis-CoT Scribe Agent."""
    profile = read_file_content(prompt_path)
    return FinRobot(
        agent_config={
            "name": "Thesis_CoT_Scribe",
            "description": "Compliance documentarian that writes override narrative justifications for portfolio drifts.",
            "profile": profile,
            "toolkits": []
        },
        llm_config=llm_config
    )


def setup_sentiment_pipeline_agents(
    llm_config: dict,
    base_llm_config: dict,
    kimi_llm_config: dict,
    prompt_dir: str,
    schema_dir: str
) -> dict:
    """Instantiates and configures all five pipeline agents, applying name stripping hooks.
    
    Returns a dictionary of:
        {
            "user_proxy": user_proxy,
            "scorer_agent": scorer_agent,
            "cio_agent": cio_agent,
            "textual_inertia_agent": textual_inertia_agent,
            "tension_extractor_agent": tension_extractor_agent,
            "scribe_agent": scribe_agent
        }
    """
    import os
    from autogen import UserProxyAgent
    from .utils.common.read_and_clean import strip_name_hook

    user_proxy = UserProxyAgent(
        name="User_Proxy",
        human_input_mode="NEVER",
        is_termination_msg=lambda x: x.get("content", "") and "TERMINATE" in x.get("content", ""),
        max_consecutive_auto_reply=15,
        code_execution_config={"use_docker": False}
    )
    
    scorer_agent = create_scorer_agent(
        prompt_path=os.path.join(prompt_dir, "sentiment_prompt.txt"),
        schema_path=os.path.join(schema_dir, "scorer_schema.json"),
        llm_config=llm_config
    )
    
    cio_agent = create_cio_agent(
        prompt_path=os.path.join(prompt_dir, "cio_prompt.txt"),
        schema_path=os.path.join(schema_dir, "sentiment_schema.json"),
        output_schema_path=os.path.join(schema_dir, "cio_output_schema.json"),
        scored_articles_path=os.path.join(schema_dir, "cio_scored_articles.json"),
        llm_config=base_llm_config
    )

    textual_inertia_agent = create_textual_inertia_agent(
        prompt_path=os.path.join(prompt_dir, "textual_inertia_prompt.txt"),
        llm_config=kimi_llm_config
    )

    tension_extractor_agent = create_tension_extractor_agent(
        prompt_path=os.path.join(prompt_dir, "tension_extractor_prompt.txt"),
        llm_config=kimi_llm_config
    )

    scribe_agent = create_scribe_agent(
        prompt_path=os.path.join(prompt_dir, "scribe_prompt.txt"),
        llm_config=kimi_llm_config
    )

    # Register strip name hooks to avoid NIM errors
    agents_list = [user_proxy, scorer_agent, cio_agent, textual_inertia_agent, tension_extractor_agent, scribe_agent]
    for agent in agents_list:
        agent.register_hook(
            hookable_method="process_all_messages_before_reply",
            hook=strip_name_hook
        )

    return {
        "user_proxy": user_proxy,
        "scorer_agent": scorer_agent,
        "cio_agent": cio_agent,
        "textual_inertia_agent": textual_inertia_agent,
        "tension_extractor_agent": tension_extractor_agent,
        "scribe_agent": scribe_agent
    }