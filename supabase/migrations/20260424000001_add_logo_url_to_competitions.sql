ALTER TABLE competitions ADD COLUMN logo_url TEXT;

UPDATE competitions
SET logo_url = 'https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/lec.webp'
WHERE name LIKE 'LEC%';
