-- MySQL schema for the Greek fuel prices database.

CREATE TABLE prefectures (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE fuel_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE daily_fuel_prices (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    prefecture_id INT NOT NULL,
    fuel_type_id INT NOT NULL,
    date DATE NOT NULL,
    price DECIMAL(6, 3) NOT NULL,

    CONSTRAINT fk_price_prefecture FOREIGN KEY (prefecture_id) REFERENCES prefectures(id),
    CONSTRAINT fk_price_fuel       FOREIGN KEY (fuel_type_id)  REFERENCES fuel_types(id),
    CONSTRAINT unique_price_entry  UNIQUE (prefecture_id, fuel_type_id, date),

    INDEX idx_prices_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
