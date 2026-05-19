CREATE TABLE taches(
            id SERIAL,
            Chat_id BIGINT,
            titre TEXT,
            date_limite INTEGER,
            note TEXT,
            statut TEXT DEFAULT 'EN_COURS',
            Days TEXT,
            CONSTRAINT PK_taches PRIMARY KEY(id)
);
CREATE TABLE notification(
            id SERIAL,
            tache_id INTEGER CONSTRAINT FK_tache_id REFERENCES taches(id) ON UPDATE CASCADE ON DELETE Set NULL,
            date_to_send INTEGER,
            message TEXT,
            name_times TEXT,
            envoye INTEGER DEFAULT 0,
            CONSTRAINT PK_notification PRIMARY KEY(id)
);
CREATE TABLE IF NOT EXISTS pile_historique (
    id SERIAL PRIMARY KEY,
    donnees JSONB NOT NULL,
    cree_le TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);