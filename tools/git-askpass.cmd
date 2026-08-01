@echo off
REM GIT_ASKPASS helper for the server's daily push.
REM
REM Git invokes this when it needs a credential. The remote URL carries the
REM username (x-access-token), so the only thing ever asked for is the password,
REM and the answer is the token in EUQUOTA_TOKEN_FILE.
REM
REM Why this exists rather than putting the token in the remote URL or on a
REM command line: arguments are visible in the process list to every account on
REM this shared machine, and a token in .git/config would be captured by the
REM Acronis backup along with the rest of the folder.
type "%EUQUOTA_TOKEN_FILE%"
