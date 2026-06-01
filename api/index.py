"""Vercel Python Function entrypoint for TH-EVI."""

from th_evi.api import app as th_evi_app


app = th_evi_app
