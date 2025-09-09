-- Create a read-only MySQL user for the bot (adjust host/password/db names to your environment).
CREATE USER IF NOT EXISTS 'acbot_ro'@'%' IDENTIFIED BY 'CHANGE_ME';
GRANT SELECT ON acore_auth.*       TO 'acbot_ro'@'%';
GRANT SELECT ON acore_characters.* TO 'acbot_ro'@'%';
GRANT SELECT ON acore_world.*      TO 'acbot_ro'@'%';
FLUSH PRIVILEGES;

