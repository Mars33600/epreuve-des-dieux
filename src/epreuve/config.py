"""Lecture de la configuration depuis les variables d'environnement (et un fichier `.env` en local).

pydantic-settings vérifie les types au démarrage : une variable manquante ou mal formée
fait échouer le programme tout de suite, avec un message clair, plutôt qu'au premier usage.
Les secrets sont des `SecretStr` : ils s'affichent `**********` dans les journaux.

Au lot A (le teaser), toutes les variables ont une valeur par défaut : le site démarre sans base
ni Discord. Les variables du lot B s'ajoutent ici (ARCHITECTURE §11).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from epreuve.domaine.mode_site import ReglageMode

OUVERTURE_PAR_DEFAUT = datetime.fromisoformat("2026-11-13T17:00:00+01:00")  # vendredi 13/11, 17 h à Paris


class Config(BaseSettings):
    # env_ignore_empty : une variable vide dans .env (« SITE_URL= ») vaut « absente » et prend sa valeur par défaut.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True)

    # --- Le mode du site (lot A, ARCHITECTURE §7.1) ---
    site_mode: ReglageMode = Field(default="auto", alias="SITE_MODE")
    site_ouvert_le: datetime = Field(default=OUVERTURE_PAR_DEFAUT, alias="SITE_OUVERT_LE")
    teaser_lien_entrer: str = Field(default="", alias="TEASER_LIEN_ENTRER")  # vide : bouton masqué
    site_url: str | None = Field(default=None, alias="SITE_URL")  # ex. https://<domaine> (Origin attendu au lot B)
    fuseau: str = Field(default="Europe/Paris", alias="FUSEAU")

    # --- Le serveur ---
    site_port: int = Field(default=8080, alias="SITE_PORT")
    journal_niveau: str = Field(default="INFO", alias="JOURNAL_NIVEAU")

    # --- Facultative au lot A : sans elle, /sante répond « base absente » ---
    database_url: SecretStr | None = Field(default=None, alias="DATABASE_URL")

    @field_validator("site_ouvert_le")
    @classmethod
    def _avec_fuseau(cls, v: datetime) -> datetime:
        # Sans fuseau, « 17:00 » serait lu à l'heure de la machine Fly (UTC) : une heure trop tard.
        if v.tzinfo is None:
            raise ValueError("SITE_OUVERT_LE doit porter son fuseau, ex. 2026-11-13T17:00:00+01:00")
        return v

    @field_validator("database_url")
    @classmethod
    def _url_asyncpg(cls, v: SecretStr | None) -> SecretStr | None:
        if v is not None and not v.get_secret_value().startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL doit commencer par postgresql+asyncpg://")
        return v
