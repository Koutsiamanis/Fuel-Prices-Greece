The database schema:
-- Creation of a table for the prefectures
CREATE TABLE prefectures (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- Creation of a table for fuel types
CREATE TABLE fuel_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- Creation of the Price Table (linking Prefecture, Fuel, Date, Price)
CREATE TABLE daily_fuel_prices (
    id BIGSERIAL PRIMARY KEY,
    prefecture_id INTEGER NOT NULL REFERENCES prefectures(id),
    fuel_type_id INTEGER NOT NULL REFERENCES fuel_types(id),
    date DATE NOT NULL,
    price NUMERIC(6, 3) NOT NULL, -- Π.χ. 1.743 (επιτρέπει 3 δεκαδικά)
    
    -- Contraint: A county, for a fuel, on a given date has only one price.
    CONSTRAINT unique_price_entry UNIQUE (prefecture_id, fuel_type_id, date)
);

-- Create an index for quick search by date
CREATE INDEX idx_prices_date ON daily_fuel_prices(date);

INSERT INTO fuel_types (name) VALUES 
('Αμόλυβδη 95 οκτ.'),
('Αμόλυβδη 100 οκτ.'),
('Diesel Κίνησης'),
('Υγραέριο κίνησης (Autogas)'),
('Diesel Θέρμανσης Κατ΄ οίκον');

INSERT INTO prefectures (name) VALUES 
('ΝΟΜΟΣ ΑΤΤΙΚΗΣ'),
('ΝΟΜΟΣ ΑΙΤΩΛΙΑΣ ΚΑΙ ΑΚΑΡΝΑΝΙΑΣ'),
('ΝΟΜΟΣ ΑΡΓΟΛΙΔΟΣ'),
('ΝΟΜΟΣ ΑΡΚΑΔΙΑΣ'),
('ΝΟΜΟΣ ΑΡΤΗΣ'),
('ΝΟΜΟΣ ΑΧΑΪΑΣ'),
('ΝΟΜΟΣ ΒΟΙΩΤΙΑΣ'),
('ΝΟΜΟΣ ΓΡΕΒΕΝΩΝ'),
('ΝΟΜΟΣ ΔΡΑΜΑΣ'),
('ΝΟΜΟΣ ΔΩΔΕΚΑΝΗΣΟΥ'),
('ΝΟΜΟΣ ΕΒΡΟΥ'),
('ΝΟΜΟΣ ΕΥΒΟΙΑΣ'),
('ΝΟΜΟΣ ΕΥΡΥΤΑΝΙΑΣ'),
('ΝΟΜΟΣ ΖΑΚΥΝΘΟΥ'),
('ΝΟΜΟΣ ΗΛΕΙΑΣ'),
('ΝΟΜΟΣ ΗΜΑΘΙΑΣ'),
('ΝΟΜΟΣ ΗΡΑΚΛΕΙΟΥ'),
('ΝΟΜΟΣ ΘΕΣΠΡΩΤΙΑΣ'),
('ΝΟΜΟΣ ΘΕΣΣΑΛΟΝΙΚΗΣ'),
('ΝΟΜΟΣ ΙΩΑΝΝΙΝΩΝ'),
('ΝΟΜΟΣ ΚΑΒΑΛΑΣ'),
('ΝΟΜΟΣ ΚΑΡΔΙΤΣΗΣ'),
('ΝΟΜΟΣ ΚΑΣΤΟΡΙΑΣ'),
('ΝΟΜΟΣ ΚΕΡΚΥΡΑΣ'),
('ΝΟΜΟΣ ΚΕΦΑΛΛΗΝΙΑΣ'),
('ΝΟΜΟΣ ΚΙΛΚΙΣ'),
('ΝΟΜΟΣ ΚΟΖΑΝΗΣ'),
('ΝΟΜΟΣ ΚΟΡΙΝΘΙΑΣ'),
('ΝΟΜΟΣ ΚΥΚΛΑΔΩΝ'),
('ΝΟΜΟΣ ΛΑΚΩΝΙΑΣ'),
('ΝΟΜΟΣ ΛΑΡΙΣΗΣ'),
('ΝΟΜΟΣ ΛΑΣΙΘΙΟΥ'),
('ΝΟΜΟΣ ΛΕΣΒΟΥ'),
('ΝΟΜΟΣ ΛΕΥΚΑΔΟΣ'),
('ΝΟΜΟΣ ΜΑΓΝΗΣΙΑΣ'),
('ΝΟΜΟΣ ΜΕΣΣΗΝΙΑΣ'),
('ΝΟΜΟΣ ΞΑΝΘΗΣ'),
('ΝΟΜΟΣ ΠΕΛΛΗΣ'),
('ΝΟΜΟΣ ΠΙΕΡΙΑΣ'),
('ΝΟΜΟΣ ΠΡΕΒΕΖΗΣ'),
('ΝΟΜΟΣ ΡΕΘΥΜΝΗΣ'),
('ΝΟΜΟΣ ΡΟΔΟΠΗΣ'),
('ΝΟΜΟΣ ΣΑΜΟΥ'),
('ΝΟΜΟΣ ΣΕΡΡΩΝ'),
('ΝΟΜΟΣ ΤΡΙΚΑΛΩΝ'),
('ΝΟΜΟΣ ΦΘΙΩΤΙΔΟΣ'),
('ΝΟΜΟΣ ΦΛΩΡΙΝΗΣ'),
('ΝΟΜΟΣ ΦΩΚΙΔΟΣ'),
('ΝΟΜΟΣ ΧΑΛΚΙΔΙΚΗΣ'),
('ΝΟΜΟΣ ΧΑΝΙΩΝ'),
('ΝΟΜΟΣ ΧΙΟΥ'),
('ΠΑΝΕΛΛΗΝΙΟΣ ΣΤΑΘΜΙΣΜΕΝΟΣ Μ.Ο.');