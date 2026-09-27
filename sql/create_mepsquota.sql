/* ---------------------------------------------------------------------------
   create_mepsquota.sql -- the SQL Server home of the tracker read model.

   Creates the MEPSQuota database on the local instance with an explicit size
   cap, SIMPLE recovery, and no auto-close/auto-shrink. The instance template
   (model) is UNLIMITED, so without the MAXSIZE clauses a new database would
   inherit no cap at all.

   Re-runnable: if the database already exists nothing is created; the ALTERs
   below simply re-assert the settings. File paths come from the instance's
   own defaults, so the script runs unchanged on another server.

   Tables are NOT created here. `python -m webapp.etl --rebuild` creates them
   from webapp/db.py (SQLAlchemy create_all) and loads the full history from
   the canonical CSVs. The CSVs stay the source of truth; this database is a
   derived copy that a --rebuild restores in about a minute.

   Run as a sysadmin with Windows authentication:
       sqlcmd -S localhost -E -b -i sql\create_mepsquota.sql
   --------------------------------------------------------------------------- */
SET NOCOUNT ON;

IF DB_ID(N'MEPSQuota') IS NULL
BEGIN
    DECLARE @data nvarchar(260) = CAST(SERVERPROPERTY('InstanceDefaultDataPath') AS nvarchar(260));
    DECLARE @log  nvarchar(260) = CAST(SERVERPROPERTY('InstanceDefaultLogPath')  AS nvarchar(260));
    IF RIGHT(@data, 1) <> N'\' SET @data = @data + N'\';
    IF RIGHT(@log,  1) <> N'\' SET @log  = @log  + N'\';

    -- Data: 64 MB start, 64 MB steps, 2 GB ceiling (~200x today's volume).
    -- Log:  64 MB start, 64 MB steps, 1 GB ceiling. Each daily ETL rewrites the
    --       whole history in one transaction, so the log must hold a full
    --       rewrite; watch its high-water mark as the history grows.
    DECLARE @sql nvarchar(max) =
        N'CREATE DATABASE [MEPSQuota] ON PRIMARY ' +
        N'(NAME = N''MEPSQuota'', FILENAME = N''' + @data + N'MEPSQuota.mdf'', ' +
        N'SIZE = 64MB, FILEGROWTH = 64MB, MAXSIZE = 2048MB) ' +
        N'LOG ON (NAME = N''MEPSQuota_log'', FILENAME = N''' + @log + N'MEPSQuota_log.ldf'', ' +
        N'SIZE = 64MB, FILEGROWTH = 64MB, MAXSIZE = 1024MB);';
    EXEC (@sql);
    PRINT 'Created MEPSQuota.';
END
ELSE
    PRINT 'MEPSQuota already exists -- re-asserting settings only.';

ALTER DATABASE [MEPSQuota] SET RECOVERY SIMPLE;
ALTER DATABASE [MEPSQuota] SET AUTO_CLOSE OFF;
ALTER DATABASE [MEPSQuota] SET AUTO_SHRINK OFF;
