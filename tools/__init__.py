# -*- coding: utf-8 -*-
"""Operational tooling for the company-server deployment.

Kept out of src/ deliberately: src/ is the scraping and reporting pipeline,
which must stay portable and dependency-light. Everything here is about the
one host the daily job runs on -- transport, credentials and scheduling -- and
none of it is imported by the pipeline.
"""
