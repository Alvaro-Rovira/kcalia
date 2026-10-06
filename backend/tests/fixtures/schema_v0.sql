-- Esquema de Kcalia antes de mejoras-v2 (user_version 0), volcado de sqlite_master.
CREATE TABLE achievements (
	"key" VARCHAR(40) NOT NULL, 
	unlocked_at DATETIME NOT NULL, 
	PRIMARY KEY ("key")
);
CREATE TABLE ai_usage (
	id INTEGER NOT NULL, 
	date VARCHAR(10) NOT NULL, 
	kind VARCHAR(8) NOT NULL, 
	calls INTEGER NOT NULL, 
	prompt_tokens INTEGER NOT NULL, 
	completion_tokens INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE counters (
	"key" VARCHAR(40) NOT NULL, 
	value INTEGER NOT NULL, 
	PRIMARY KEY ("key")
);
CREATE TABLE dish_aliases (
	norm VARCHAR(400) NOT NULL, 
	dish_id INTEGER NOT NULL, 
	PRIMARY KEY (norm), 
	FOREIGN KEY(dish_id) REFERENCES dishes (id) ON DELETE CASCADE
);
CREATE TABLE dishes (
	id INTEGER NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	text TEXT NOT NULL, 
	norm VARCHAR(400) NOT NULL, 
	items JSON NOT NULL, 
	kcal FLOAT NOT NULL, 
	protein FLOAT NOT NULL, 
	carbs FLOAT NOT NULL, 
	fat FLOAT NOT NULL, 
	confidence FLOAT NOT NULL, 
	assumptions JSON NOT NULL, 
	origin VARCHAR(12) NOT NULL, 
	favorite BOOLEAN NOT NULL, 
	use_count INTEGER NOT NULL, 
	last_used_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE foods (
	id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	norm VARCHAR(160) NOT NULL, 
	kcal100 FLOAT NOT NULL, 
	protein100 FLOAT NOT NULL, 
	carbs100 FLOAT NOT NULL, 
	fat100 FLOAT NOT NULL, 
	unit_grams JSON NOT NULL, 
	hits INTEGER NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE meals (
	id INTEGER NOT NULL, 
	client_id VARCHAR(40) NOT NULL, 
	date VARCHAR(10) NOT NULL, 
	slot VARCHAR(12) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	text TEXT NOT NULL, 
	items JSON NOT NULL, 
	servings FLOAT NOT NULL, 
	kcal FLOAT NOT NULL, 
	protein FLOAT NOT NULL, 
	carbs FLOAT NOT NULL, 
	fat FLOAT NOT NULL, 
	source VARCHAR(12) NOT NULL, 
	confidence FLOAT NOT NULL, 
	assumptions JSON NOT NULL, 
	dish_id INTEGER, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(dish_id) REFERENCES dishes (id) ON DELETE SET NULL
);
CREATE TABLE product_images (
	product_id INTEGER NOT NULL, 
	mime VARCHAR(30) NOT NULL, 
	data BLOB NOT NULL, 
	PRIMARY KEY (product_id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE TABLE products (
	id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	alias VARCHAR(60) NOT NULL, 
	basis VARCHAR(2) NOT NULL, 
	kcal100 FLOAT NOT NULL, 
	protein100 FLOAT NOT NULL, 
	carbs100 FLOAT NOT NULL, 
	fat100 FLOAT NOT NULL, 
	fiber100 FLOAT, 
	sugars100 FLOAT, 
	salt100 FLOAT, 
	unit_label VARCHAR(30) NOT NULL, 
	unit_grams FLOAT, 
	has_image BOOLEAN NOT NULL, 
	use_count INTEGER NOT NULL, 
	last_used_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE profile (
	id INTEGER NOT NULL, 
	sex VARCHAR(8) NOT NULL, 
	age INTEGER NOT NULL, 
	height_cm FLOAT NOT NULL, 
	weight_kg FLOAT NOT NULL, 
	activity VARCHAR(16) NOT NULL, 
	goal VARCHAR(24) NOT NULL, 
	target_weight_kg FLOAT, 
	weight_unit VARCHAR(4) NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE sessions (
	id INTEGER NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	user_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	last_seen DATETIME NOT NULL, 
	expires_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE TABLE targets (
	id INTEGER NOT NULL, 
	kcal INTEGER NOT NULL, 
	protein INTEGER NOT NULL, 
	carbs INTEGER NOT NULL, 
	fat INTEGER NOT NULL, 
	bmr INTEGER NOT NULL, 
	tdee INTEGER NOT NULL, 
	custom BOOLEAN NOT NULL, 
	basis_weight_kg FLOAT NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE users (
	id INTEGER NOT NULL, 
	username VARCHAR(64) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username)
);
CREATE TABLE weekly_summaries (
	id INTEGER NOT NULL, 
	week_start VARCHAR(10) NOT NULL, 
	data JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE weights (
	id INTEGER NOT NULL, 
	date VARCHAR(10) NOT NULL, 
	kg FLOAT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_ai_usage_date ON ai_usage (date);
CREATE INDEX ix_dish_aliases_dish_id ON dish_aliases (dish_id);
CREATE UNIQUE INDEX ix_dishes_norm ON dishes (norm);
CREATE UNIQUE INDEX ix_foods_norm ON foods (norm);
CREATE UNIQUE INDEX ix_meals_client_id ON meals (client_id);
CREATE INDEX ix_meals_date ON meals (date);
CREATE INDEX ix_meals_date_live ON meals (date, deleted_at);
CREATE UNIQUE INDEX ix_sessions_token_hash ON sessions (token_hash);
CREATE UNIQUE INDEX ix_weekly_summaries_week_start ON weekly_summaries (week_start);
CREATE UNIQUE INDEX ix_weights_date ON weights (date);
CREATE UNIQUE INDEX ux_ai_usage_date_kind ON ai_usage (date, kind);
