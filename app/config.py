from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""

    # Supabase project connection info (Project Settings -> API / Database in the Supabase dashboard)
    database_url: str = ""
    supabase_url: str = ""
    supabase_secret_key: str = ""
    demo_user_id: str = ""

    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"
    plaid_token_encryption_key: str = ""


settings = Settings()
