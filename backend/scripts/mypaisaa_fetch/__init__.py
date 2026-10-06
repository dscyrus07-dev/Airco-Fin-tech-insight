"""MyPaisaa bank statement fetching pipeline.

Fetches ALL bank statements for a list of MyPaisaa user IDs via the
customerbankdetails API, downloads every statement, deduplicates them and
maintains a restartable SQLite manifest.

Run from ``backend/``::

    python -m scripts.mypaisaa_fetch --input "../New Dataset/users.csv"
"""
