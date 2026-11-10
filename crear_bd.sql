-- =====================================================================
-- Laboratorio de Aplicaciones II - 6° G
-- TP N° 15: Operaciones CRUD con bases de datos en Python
-- Temática: Sistema de gestión de un pañol de herramientas
-- Archivo: crear_bd.sql
-- =====================================================================
-- NOTA: si tu servidor en la nube (por ejemplo Clever Cloud) ya te da la
-- base creada y no te deja usar CREATE DATABASE, comentá las dos primeras
-- sentencias y ejecutá el resto sobre la base que te asignaron.
-- =====================================================================

-- Forzar UTF-8 en esta sesión (evita que se rompan las tildes y la ñ)
SET NAMES utf8mb4;

-- 1) Crear la base de datos (con soporte para tildes y la letra ñ)
CREATE DATABASE IF NOT EXISTS panol_herramientas
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- Seleccionar la base para trabajar sobre ella
USE panol_herramientas;

-- 2) Tabla de categorías de herramientas
CREATE TABLE IF NOT EXISTS categorias (
    id          INT AUTO_INCREMENT PRIMARY KEY,   -- clave primaria autoincremental
    nombre      VARCHAR(100) NOT NULL,
    descripcion TEXT
) ENGINE = InnoDB;

-- 3) Tabla principal: herramientas (sobre ella se hace el CRUD)
CREATE TABLE IF NOT EXISTS herramientas (
    id                INT AUTO_INCREMENT PRIMARY KEY,   -- clave primaria autoincremental
    nombre            VARCHAR(100) NOT NULL,
    marca             VARCHAR(50),
    modelo            VARCHAR(50),
    id_categoria      INT,                              -- clave foránea hacia categorias
    estado            ENUM('Disponible', 'Prestado', 'Mantenimiento', 'Dañado')
                      NOT NULL DEFAULT 'Disponible',
    fecha_adquisicion DATE,
    FOREIGN KEY (id_categoria) REFERENCES categorias(id)
) ENGINE = InnoDB;

-- 4) Tabla de personas (empleados que pueden pedir herramientas)
CREATE TABLE IF NOT EXISTS personas (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    nombre       VARCHAR(100) NOT NULL,
    departamento VARCHAR(50),
    email        VARCHAR(100)
) ENGINE = InnoDB;

-- 5) Tabla de préstamos (relaciona herramientas con personas)
CREATE TABLE IF NOT EXISTS prestamos (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    id_herramienta   INT NOT NULL,
    id_persona       INT NOT NULL,
    fecha_prestamo   DATE NOT NULL,
    fecha_devolucion DATE,                              -- NULL = todavía no se devolvió
    observaciones    TEXT,
    FOREIGN KEY (id_herramienta) REFERENCES herramientas(id),
    FOREIGN KEY (id_persona)     REFERENCES personas(id)
) ENGINE = InnoDB;

-- =====================================================================
-- DATOS DE PRUEBA
-- (si ejecutás el script dos veces sobre las mismas tablas, los INSERT
--  se duplican; para empezar de cero usá DROP TABLE antes)
-- =====================================================================

INSERT INTO categorias (nombre, descripcion) VALUES
('Herramientas Manuales',   'Destornilladores, martillos, alicates, etc.'),
('Herramientas Eléctricas', 'Taladros, amoladoras, sierras eléctricas'),
('Medición y Precisión',    'Calibres, micrómetros, niveles'),
('Sujeción',                'Sargentos, prensas, tornillos de banco');

INSERT INTO herramientas (nombre, marca, modelo, id_categoria, estado, fecha_adquisicion) VALUES
('Martillo de Bola',       'Stanley',   'MB-500',     1, 'Disponible',    '2024-01-15'),
('Destornillador Phillips','Bahco',     'PH2',        1, 'Prestado',      '2024-02-20'),
('Taladro Percutor',       'Bosch',     'GBM 13-2',   2, 'Disponible',    '2024-03-10'),
('Calibre Digital',        'Mitutoyo',  '500-196-30', 3, 'Mantenimiento', '2024-01-30'),
('Alicate Universal',      'Irwin',     '8IN',        1, 'Disponible',    '2024-02-28'),
('Sargento de Presión',    'Bessey',    'GSV-300',    4, 'Disponible',    '2024-04-05');

INSERT INTO personas (nombre, departamento, email) VALUES
('Juan Pérez',   'Taller',        'juan.perez@empresa.com'),
('María García', 'Mantenimiento', 'maria.garcia@empresa.com'),
('Carlos López', 'Producción',    'carlos.lopez@empresa.com');

-- El préstamo 1 sigue activo (sin devolución) y el 2 ya fue devuelto
INSERT INTO prestamos (id_herramienta, id_persona, fecha_prestamo, fecha_devolucion, observaciones) VALUES
(2, 1, '2024-10-01', NULL,         'Prestado para reparación urgente'),
(4, 2, '2024-09-28', '2024-10-02', 'Devolución con desgaste normal');
