"""Lecture de la configuration depuis les variables d'environnement (et un fichier `.env` en local).

pydantic-settings vérifie les types au démarrage : une variable manquante ou mal formée
fait échouer le programme tout de suite, avec un message clair, plutôt qu'au premier usage.
Les secrets sont des `SecretStr` : ils s'affichent `**********` dans les journaux.
"""

from __future__ import annotations

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Obligatoires dès le jalon bêta ---
    discord_token: SecretStr = Field(alias="DISCORD_TOKEN")
    discord_guild_id: int = Field(alias="DISCORD_GUILD_ID")
    discord_admin_role_id: int = Field(alias="DISCORD_ADMIN_ROLE_ID")
    discord_screen_channel_id: int = Field(alias="DISCORD_SCREEN_CHANNEL_ID")
    database_url: SecretStr = Field(alias="DATABASE_URL")
    site_port: int = Field(default=8080, alias="SITE_PORT")
    fuseau: str = Field(default="Europe/Paris", alias="FUSEAU")
    journal_niveau: str = Field(default="INFO", alias="JOURNAL_NIVEAU")

    # --- Réservées au jalon lancement, facultatives en bêta ---
    discord_admin_channel_id: int | None = Field(default=None, alias="DISCORD_ADMIN_CHANNEL_ID")
    discord_annonce_channel_id: int | None = Field(default=None, alias="DISCORD_ANNONCE_CHANNEL_ID")
    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    supabase_service_key: SecretStr | None = Field(default=None, alias="SUPABASE_SERVICE_KEY")
    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    ia_active: bool = Field(default=False, alias="IA_ACTIVE")
    ia_modele: str = Field(default="claude-haiku-5-5", alias="IA_MODELE")

    @field_validator("database_url")
    @classmethod
    def _url_asyncpg(cls, v: SecretStr) -> SecretStr:
        if not v.get_secret_value().startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL doit commencer par postgresql+asyncpg://")
        return v
