-- ============================================================
-- BOOKSTORE DATABASE SCHEMA
-- ============================================================

-- DDL: CREATE DATABASE
CREATE DATABASE IF NOT EXISTS bookstore_db;
USE bookstore_db;

-- DCL: GRANT privileges (run as root)
-- GRANT ALL PRIVILEGES ON bookstore_db.* TO 'bookstore_user'@'localhost' IDENTIFIED BY 'Oracle04';
-- FLUSH PRIVILEGES;

-- ============================================================
-- DDL: CREATE TABLES
-- ============================================================

-- CUSTOMER TABLE
CREATE TABLE IF NOT EXISTS CUSTOMER (
    CUST_ID INT AUTO_INCREMENT PRIMARY KEY,
    FIRST_NAME VARCHAR(50) NOT NULL,
    LAST_NAME VARCHAR(50) NOT NULL,
    PHONE_NUMBER VARCHAR(15),
    EMAIL VARCHAR(100) UNIQUE NOT NULL,
    HOUSE_NUMBER VARCHAR(20),
    STREET VARCHAR(100),
    CITY VARCHAR(50),
    STATE VARCHAR(50),
    PINCODE VARCHAR(10),
    USERNAME VARCHAR(50) UNIQUE NOT NULL,
    PASSWORD_HASH VARCHAR(255) NOT NULL,
    CREATED_AT DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- PUBLISHER TABLE
CREATE TABLE IF NOT EXISTS PUBLISHER_DETAILS (
    P_ID INT AUTO_INCREMENT PRIMARY KEY,
    NAME VARCHAR(100) NOT NULL,
    ADDRESS VARCHAR(255),
    EMAIL VARCHAR(100),
    PHONE_NUMBER VARCHAR(15)
);

-- AUTHOR TABLE
CREATE TABLE IF NOT EXISTS AUTHOR (
    A_ID INT AUTO_INCREMENT PRIMARY KEY,
    NAME VARCHAR(100) NOT NULL,
    EMAIL VARCHAR(100),
    PHONE VARCHAR(15)
);

-- BOOK TABLE
CREATE TABLE IF NOT EXISTS BOOK (
    ISBN VARCHAR(20) PRIMARY KEY,
    TITLE VARCHAR(200) NOT NULL,
    EDITION VARCHAR(20),
    PRICE DECIMAL(10,2) NOT NULL,
    PUBLICATION_YEAR INT,
    LANGUAGE VARCHAR(50),
    QUANTITY_AVAILABLE INT DEFAULT 0,
    P_ID INT,
    A_ID INT,
    IMAGE_PATH VARCHAR(255),
    FOREIGN KEY (P_ID) REFERENCES PUBLISHER_DETAILS(P_ID) ON DELETE SET NULL,
    FOREIGN KEY (A_ID) REFERENCES AUTHOR(A_ID) ON DELETE SET NULL
);

-- ORDERS TABLE
CREATE TABLE IF NOT EXISTS `ORDER` (
    O_ID INT AUTO_INCREMENT PRIMARY KEY,
    CUST_ID INT,
    ORDER_DATE DATE DEFAULT (CURRENT_DATE),
    ORDER_STATUS ENUM('Pending','Processing','Shipped','Completed','Cancelled') DEFAULT 'Pending',
    HOUSE_NUMBER VARCHAR(20),
    STREET VARCHAR(100),
    CITY VARCHAR(50),
    STATE VARCHAR(50),
    PINCODE VARCHAR(10),
    NOS_OF_BOOKS_ORDERED INT,
    TOTAL_AMOUNT DECIMAL(10,2),
    FOREIGN KEY (CUST_ID) REFERENCES CUSTOMER(CUST_ID) ON DELETE SET NULL
);

-- ORDER_ITEMS TABLE (books in an order)
CREATE TABLE IF NOT EXISTS ORDER_ITEMS (
    ITEM_ID INT AUTO_INCREMENT PRIMARY KEY,
    O_ID INT,
    ISBN VARCHAR(20),
    BOOK_TITLE VARCHAR(200),
    QUANTITY INT,
    UNIT_PRICE DECIMAL(10,2),
    FOREIGN KEY (O_ID) REFERENCES `ORDER`(O_ID) ON DELETE CASCADE,
    FOREIGN KEY (ISBN) REFERENCES BOOK(ISBN) ON DELETE SET NULL
);

-- PAYMENT TABLE
CREATE TABLE IF NOT EXISTS PAYMENT (
    PAY_ID INT AUTO_INCREMENT PRIMARY KEY,
    O_ID INT,
    AMOUNT_TOTAL DECIMAL(10,2),
    METHOD ENUM('Credit Card','Debit Card','UPI','Net Banking','Cash on Delivery') NOT NULL,
    PAYMENT_DATE DATE DEFAULT (CURRENT_DATE),
    PAYMENT_STATUS ENUM('Pending','Completed','Failed','Refunded') DEFAULT 'Pending',
    TRANSACTION_ID VARCHAR(100) UNIQUE,
    FOREIGN KEY (O_ID) REFERENCES `ORDER`(O_ID) ON DELETE CASCADE
);

-- AUDIT LOG TABLE (for triggers)
CREATE TABLE IF NOT EXISTS AUDIT_LOG (
    LOG_ID INT AUTO_INCREMENT PRIMARY KEY,
    ACTION_TYPE VARCHAR(50),
    TABLE_NAME VARCHAR(50),
    RECORD_ID VARCHAR(50),
    ACTION_TIME DATETIME DEFAULT CURRENT_TIMESTAMP,
    DETAILS TEXT
);

-- SEARCH_LOG TABLE (for trigger on not found)
CREATE TABLE IF NOT EXISTS SEARCH_LOG (
    SEARCH_ID INT AUTO_INCREMENT PRIMARY KEY,
    SEARCH_TYPE VARCHAR(50),
    SEARCH_TERM VARCHAR(200),
    RESULT VARCHAR(100),
    SEARCHED_AT DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- DDL: ALTER TABLE examples
-- ============================================================
-- ALTER TABLE BOOK ADD COLUMN IF NOT EXISTS DESCRIPTION TEXT;
-- ALTER TABLE CUSTOMER ADD COLUMN IF NOT EXISTS LOYALTY_POINTS INT DEFAULT 0;

-- ============================================================
-- TRIGGERS
-- ============================================================

DELIMITER $$

-- TRIGGER 1: AFTER INSERT on ORDER_ITEMS - decrease book quantity
CREATE TRIGGER IF NOT EXISTS after_order_item_insert
AFTER INSERT ON ORDER_ITEMS
FOR EACH ROW
BEGIN
    UPDATE BOOK SET QUANTITY_AVAILABLE = QUANTITY_AVAILABLE - NEW.QUANTITY
    WHERE ISBN = NEW.ISBN;
    INSERT INTO AUDIT_LOG(ACTION_TYPE, TABLE_NAME, RECORD_ID, DETAILS)
    VALUES('INSERT', 'ORDER_ITEMS', NEW.ITEM_ID,
           CONCAT('Book ISBN: ', NEW.ISBN, ' | Qty: ', NEW.QUANTITY, ' ordered'));
END$$

-- TRIGGER 2: BEFORE INSERT on BOOK - validate price and quantity
CREATE TRIGGER IF NOT EXISTS before_book_insert
BEFORE INSERT ON BOOK
FOR EACH ROW
BEGIN
    IF NEW.PRICE < 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Price cannot be negative';
    END IF;
    IF NEW.QUANTITY_AVAILABLE < 0 THEN
        SET NEW.QUANTITY_AVAILABLE = 0;
    END IF;
END$$

-- TRIGGER 3: AFTER DELETE on BOOK - log deletion
CREATE TRIGGER IF NOT EXISTS after_book_delete
AFTER DELETE ON BOOK
FOR EACH ROW
BEGIN
    INSERT INTO AUDIT_LOG(ACTION_TYPE, TABLE_NAME, RECORD_ID, DETAILS)
    VALUES('DELETE', 'BOOK', OLD.ISBN,
           CONCAT('Deleted book: ', OLD.TITLE, ' | Price: ', OLD.PRICE));
END$$

-- TRIGGER 4: BEFORE UPDATE on ORDER - log status change
CREATE TRIGGER IF NOT EXISTS before_order_update
BEFORE UPDATE ON `ORDER`
FOR EACH ROW
BEGIN
    IF OLD.ORDER_STATUS != NEW.ORDER_STATUS THEN
        INSERT INTO AUDIT_LOG(ACTION_TYPE, TABLE_NAME, RECORD_ID, DETAILS)
        VALUES('UPDATE', 'ORDER', OLD.O_ID,
               CONCAT('Status changed from ', OLD.ORDER_STATUS, ' to ', NEW.ORDER_STATUS));
    END IF;
END$$

DELIMITER ;

-- ============================================================
-- VIEWS
-- ============================================================

-- View 1: Books with author and publisher details (INNER JOIN)
CREATE OR REPLACE VIEW BOOK_FULL_DETAILS AS
SELECT
    B.ISBN,
    B.TITLE,
    B.EDITION,
    B.PRICE,
    B.PUBLICATION_YEAR,
    B.LANGUAGE,
    B.QUANTITY_AVAILABLE,
    B.IMAGE_PATH,
    A.NAME AS AUTHOR_NAME,
    A.EMAIL AS AUTHOR_EMAIL,
    A.PHONE AS AUTHOR_PHONE,
    P.NAME AS PUBLISHER_NAME,
    P.ADDRESS AS PUBLISHER_ADDRESS,
    P.EMAIL AS PUBLISHER_EMAIL,
    P.PHONE_NUMBER AS PUBLISHER_PHONE
FROM BOOK B
LEFT JOIN AUTHOR A ON B.A_ID = A.A_ID
LEFT JOIN PUBLISHER_DETAILS P ON B.P_ID = P.P_ID;

-- View 2: Order details with customer info (JOIN)
CREATE OR REPLACE VIEW ORDER_CUSTOMER_VIEW AS
SELECT
    O.O_ID,
    O.ORDER_DATE,
    O.ORDER_STATUS,
    O.TOTAL_AMOUNT,
    O.NOS_OF_BOOKS_ORDERED,
    O.HOUSE_NUMBER, O.STREET, O.CITY, O.STATE, O.PINCODE,
    C.CUST_ID,
    CONCAT(C.FIRST_NAME, ' ', C.LAST_NAME) AS CUSTOMER_NAME,
    C.EMAIL AS CUSTOMER_EMAIL,
    C.PHONE_NUMBER AS CUSTOMER_PHONE,
    P.METHOD AS PAYMENT_METHOD,
    P.PAYMENT_STATUS,
    P.TRANSACTION_ID
FROM `ORDER` O
LEFT JOIN CUSTOMER C ON O.CUST_ID = C.CUST_ID
LEFT JOIN PAYMENT P ON O.O_ID = P.O_ID;

-- View 3: Author book count
CREATE OR REPLACE VIEW AUTHOR_BOOK_COUNT AS
SELECT
    A.A_ID,
    A.NAME AS AUTHOR_NAME,
    A.EMAIL,
    A.PHONE,
    COUNT(B.ISBN) AS BOOKS_WRITTEN
FROM AUTHOR A
LEFT JOIN BOOK B ON A.A_ID = B.A_ID
GROUP BY A.A_ID, A.NAME, A.EMAIL, A.PHONE;

-- View 4: Publisher book count
CREATE OR REPLACE VIEW PUBLISHER_BOOK_COUNT AS
SELECT
    P.P_ID,
    P.NAME AS PUBLISHER_NAME,
    P.ADDRESS,
    P.EMAIL,
    P.PHONE_NUMBER,
    COUNT(B.ISBN) AS BOOKS_PUBLISHED
FROM PUBLISHER_DETAILS P
LEFT JOIN BOOK B ON P.P_ID = B.P_ID
GROUP BY P.P_ID, P.NAME, P.ADDRESS, P.EMAIL, P.PHONE_NUMBER;

-- View 5: Top ordered books (aggregate)
CREATE OR REPLACE VIEW TOP_ORDERED_BOOKS AS
SELECT
    OI.ISBN,
    OI.BOOK_TITLE,
    SUM(OI.QUANTITY) AS TOTAL_ORDERED,
    COUNT(DISTINCT OI.O_ID) AS NUM_ORDERS,
    AVG(OI.UNIT_PRICE) AS AVG_PRICE
FROM ORDER_ITEMS OI
GROUP BY OI.ISBN, OI.BOOK_TITLE
ORDER BY TOTAL_ORDERED DESC;

-- ============================================================
-- STORED PROCEDURE with CURSOR
-- ============================================================

DELIMITER $$

-- Cursor: Generate inventory report and flag low-stock books
CREATE PROCEDURE IF NOT EXISTS generate_inventory_report()
BEGIN
    DECLARE done INT DEFAULT FALSE;
    DECLARE v_isbn VARCHAR(20);
    DECLARE v_title VARCHAR(200);
    DECLARE v_qty INT;
    DECLARE v_price DECIMAL(10,2);

    DECLARE book_cursor CURSOR FOR
        SELECT ISBN, TITLE, QUANTITY_AVAILABLE, PRICE FROM BOOK ORDER BY QUANTITY_AVAILABLE ASC;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

    CREATE TEMPORARY TABLE IF NOT EXISTS INVENTORY_REPORT (
        ISBN VARCHAR(20),
        TITLE VARCHAR(200),
        QUANTITY INT,
        PRICE DECIMAL(10,2),
        STATUS VARCHAR(20)
    );

    DELETE FROM INVENTORY_REPORT;

    OPEN book_cursor;

    read_loop: LOOP
        FETCH book_cursor INTO v_isbn, v_title, v_qty, v_price;
        IF done THEN LEAVE read_loop; END IF;

        INSERT INTO INVENTORY_REPORT VALUES (
            v_isbn, v_title, v_qty, v_price,
            CASE
                WHEN v_qty = 0 THEN 'OUT OF STOCK'
                WHEN v_qty <= 5 THEN 'LOW STOCK'
                ELSE 'IN STOCK'
            END
        );
    END LOOP;

    CLOSE book_cursor;

    SELECT * FROM INVENTORY_REPORT;
END$$

-- TCL: Procedure with SAVEPOINT, COMMIT, ROLLBACK
CREATE PROCEDURE IF NOT EXISTS place_order_transaction(
    IN p_cust_id INT,
    IN p_isbn VARCHAR(20),
    IN p_qty INT,
    IN p_method VARCHAR(50),
    IN p_house VARCHAR(20),
    IN p_street VARCHAR(100),
    IN p_city VARCHAR(50),
    IN p_state VARCHAR(50),
    IN p_pincode VARCHAR(10),
    OUT p_order_id INT,
    OUT p_message VARCHAR(255)
)
BEGIN
    DECLARE v_price DECIMAL(10,2);
    DECLARE v_available INT;
    DECLARE v_total DECIMAL(10,2);
    DECLARE v_trans_id VARCHAR(100);
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_message = 'Transaction failed - rolled back';
        SET p_order_id = -1;
    END;

    START TRANSACTION;
    SAVEPOINT before_order;

    SELECT PRICE, QUANTITY_AVAILABLE INTO v_price, v_available FROM BOOK WHERE ISBN = p_isbn;

    IF v_available < p_qty THEN
        SET p_message = 'Insufficient stock';
        SET p_order_id = -1;
        ROLLBACK TO SAVEPOINT before_order;
        ROLLBACK;
    ELSE
        SET v_total = v_price * p_qty;
        SET v_trans_id = CONCAT('TXN', UNIX_TIMESTAMP(), FLOOR(RAND()*1000));

        INSERT INTO `ORDER`(CUST_ID, ORDER_STATUS, HOUSE_NUMBER, STREET, CITY, STATE, PINCODE,
                            NOS_OF_BOOKS_ORDERED, TOTAL_AMOUNT)
        VALUES (p_cust_id, 'Pending', p_house, p_street, p_city, p_state, p_pincode, p_qty, v_total);

        SET p_order_id = LAST_INSERT_ID();
        SAVEPOINT after_order;

        INSERT INTO ORDER_ITEMS(O_ID, ISBN, BOOK_TITLE, QUANTITY, UNIT_PRICE)
        SELECT p_order_id, ISBN, TITLE, p_qty, PRICE FROM BOOK WHERE ISBN = p_isbn;

        SAVEPOINT after_items;

        INSERT INTO PAYMENT(O_ID, AMOUNT_TOTAL, METHOD, PAYMENT_DATE, PAYMENT_STATUS, TRANSACTION_ID)
        VALUES(p_order_id, v_total, p_method, CURRENT_DATE, 'Completed', v_trans_id);

        COMMIT;
        SET p_message = 'Order placed successfully';
    END IF;
END$$

DELIMITER ;

-- ============================================================
-- SAMPLE DATA - DML INSERT
-- ============================================================

INSERT IGNORE INTO PUBLISHER_DETAILS(NAME, ADDRESS, EMAIL, PHONE_NUMBER) VALUES
('Penguin Books', '80 Strand, London', 'contact@penguin.com', '9876543210'),
('Oxford University Press', 'Great Clarendon Street, Oxford', 'info@oup.com', '9123456789'),
('HarperCollins', '195 Broadway, New York', 'hello@harpercollins.com', '9000011111'),
('Bloomsbury', '50 Bedford Square, London', 'info@bloomsbury.com', '9111122222'),
('Scholastic', '557 Broadway, New York', 'contact@scholastic.com', '9333344444');

INSERT IGNORE INTO AUTHOR(NAME, EMAIL, PHONE) VALUES
('J.K. Rowling', 'jk@rowling.com', '9001112222'),
('George Orwell', 'orwell@books.com', '9002223333'),
('Yuval Noah Harari', 'yuval@books.com', '9003334444'),
('Agatha Christie', 'agatha@books.com', '9004445555'),
('Dan Brown', 'dan@books.com', '9005556666');

INSERT IGNORE INTO BOOK(ISBN, TITLE, EDITION, PRICE, PUBLICATION_YEAR, LANGUAGE, QUANTITY_AVAILABLE, P_ID, A_ID) VALUES
('978-0439708180', 'Harry Potter and the Sorcerer''s Stone', '1st', 499.00, 1997, 'English', 50, 4, 1),
('978-0451524935', 'Nineteen Eighty-Four', '2nd', 350.00, 1949, 'English', 30, 1, 2),
('978-0062316097', 'Sapiens', '3rd', 599.00, 2011, 'English', 25, 3, 3),
('978-0062073488', 'Murder on the Orient Express', '1st', 299.00, 1934, 'English', 40, 3, 4),
('978-0307474278', 'The Da Vinci Code', '1st', 399.00, 2003, 'English', 35, 1, 5),
('978-0439064873', 'Harry Potter and the Chamber of Secrets', '1st', 499.00, 1998, 'English', 20, 4, 1),
('978-0198133964', 'Animal Farm', '1st', 250.00, 1945, 'English', 45, 2, 2),
('978-0062458537', 'Homo Deus', '1st', 549.00, 2015, 'English', 15, 3, 3);

-- ============================================================
-- AGGREGATE FUNCTION QUERIES
-- ============================================================

-- COUNT books per author
-- SELECT A.NAME, COUNT(B.ISBN) AS BOOK_COUNT FROM AUTHOR A LEFT JOIN BOOK B ON A.A_ID = B.A_ID GROUP BY A.A_ID;

-- SUM of total inventory value
-- SELECT SUM(PRICE * QUANTITY_AVAILABLE) AS TOTAL_INVENTORY_VALUE FROM BOOK;

-- AVG price of books
-- SELECT AVG(PRICE) AS AVERAGE_PRICE FROM BOOK;

-- MAX and MIN price
-- SELECT MAX(PRICE) AS MOST_EXPENSIVE, MIN(PRICE) AS CHEAPEST FROM BOOK;

-- HAVING: publishers with more than 2 books
-- SELECT P.NAME, COUNT(B.ISBN) AS CNT FROM PUBLISHER_DETAILS P JOIN BOOK B ON P.P_ID=B.P_ID GROUP BY P.P_ID HAVING CNT > 2;

-- ============================================================
-- STRING FUNCTION QUERIES
-- ============================================================

-- UPPER, LOWER, CONCAT, LENGTH, TRIM, SUBSTRING
-- SELECT UPPER(TITLE), LOWER(LANGUAGE), CONCAT(FIRST_NAME,' ',LAST_NAME), LENGTH(EMAIL), TRIM(PHONE) FROM BOOK B JOIN AUTHOR A ON B.A_ID=A.A_ID JOIN CUSTOMER C ON 1=1 LIMIT 5;

-- ============================================================
-- DATE FUNCTION QUERIES
-- ============================================================

-- CURRENT_DATE, DATEDIFF, EXTRACT
-- SELECT O_ID, ORDER_DATE, CURRENT_DATE, DATEDIFF(CURRENT_DATE, ORDER_DATE) AS DAYS_AGO, YEAR(ORDER_DATE) AS ORDER_YEAR, MONTH(ORDER_DATE) AS ORDER_MONTH FROM `ORDER`;

-- ============================================================
-- JOIN EXAMPLES
-- ============================================================

-- INNER JOIN: Books with authors
-- SELECT B.TITLE, A.NAME FROM BOOK B INNER JOIN AUTHOR A ON B.A_ID = A.A_ID;

-- LEFT JOIN: All authors even without books
-- SELECT A.NAME, B.TITLE FROM AUTHOR A LEFT JOIN BOOK B ON A.A_ID = B.A_ID;

-- RIGHT JOIN: All books even without authors
-- SELECT A.NAME, B.TITLE FROM AUTHOR A RIGHT JOIN BOOK B ON A.A_ID = B.A_ID;

-- SELF JOIN: Customers from same city (example)
-- SELECT A.FIRST_NAME AS C1, B.FIRST_NAME AS C2, A.CITY FROM CUSTOMER A JOIN CUSTOMER C2 ON A.CITY = B.CITY AND A.CUST_ID != B.CUST_ID;

-- ============================================================
-- WHERE, LIKE, IN, BETWEEN, DISTINCT, ORDER BY, GROUP BY
-- ============================================================

-- WHERE + LIKE
-- SELECT * FROM BOOK WHERE TITLE LIKE '%Harry%';

-- IN
-- SELECT * FROM BOOK WHERE LANGUAGE IN ('English','Hindi','French');

-- BETWEEN
-- SELECT * FROM BOOK WHERE PRICE BETWEEN 200 AND 500;

-- DISTINCT languages
-- SELECT DISTINCT LANGUAGE FROM BOOK;

-- ORDER BY
-- SELECT * FROM BOOK ORDER BY PRICE DESC;

-- ============================================================
-- DCL: REVOKE (example)
-- ============================================================
-- REVOKE DELETE ON bookstore_db.BOOK FROM 'bookstore_user'@'localhost';

-- ============================================================
-- DDL: TRUNCATE and DROP examples (commented for safety)
-- ============================================================
-- TRUNCATE TABLE AUDIT_LOG;
-- DROP TABLE IF EXISTS SEARCH_LOG;
