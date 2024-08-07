import os

from deta import Deta
from dotenv import load_dotenv
from fastapi import FastAPI

_DESC = """
An endpoint for [CocktailBerry](https://github.com/AndreWohnsland/CocktailBerry) to send cocktail data to! 🍹

## cocktail

You can **post your cocktaildata** or **get all the cocktaildata**.
Check the tags which route is public accessible and which one is protected by an API key.
Usually routes inserting or changing data are protected, routes getting data are open.

This API is still quite minimal, since not much endpoints are needed for CocktailBerry.
"""


def init_app():
    load_dotenv()
    tags_metadata = [
        {
            "name": "cocktail",
            "description": "Operations with cocktail data.",
        },
        {
            "name": "automation",
            "description": "Operations made by deta on a schedule.",
        },
        {
            "name": "protected",
            "description": "Route is protected by API key.",
        },
        {
            "name": "open",
            "description": "Route is accessible by public.",
        },
        {
            "name": "installation",
            "description": "Topics related to CocktailBerry installation.",
        },
    ]
    app = FastAPI(
        title="CocktailBerry WebApp / Dashboard API",
        version="1.0",
        description=_DESC,
        openapi_tags=tags_metadata,
    )
    is_dev = os.getenv("DEBUG") is not None
    deta = Deta(os.getenv("MY_DATA_KEY", "no_key_found"))
    return app, deta, is_dev
