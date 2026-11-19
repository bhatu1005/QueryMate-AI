-- Synthetic example rows. Run only against the local/demo querymate database.
USE querymate;

INSERT INTO customers (customer_id, customer_name, region, joined_on) VALUES
    (1, 'Avery Stone', 'West', '2024-01-15'),
    (2, 'Jordan Lee', 'East', '2024-03-02'),
    (3, 'Casey Morgan', 'Central', '2024-06-21')
ON DUPLICATE KEY UPDATE customer_name = VALUES(customer_name), region = VALUES(region), joined_on = VALUES(joined_on);

INSERT INTO orders (order_id, customer_id, order_date, amount, status) VALUES
    (1001, 1, '2025-01-10', 1250.00, 'completed'),
    (1002, 1, '2025-02-14', 450.50, 'completed'),
    (1003, 2, '2025-02-20', 980.00, 'pending'),
    (1004, 3, '2025-03-05', 1725.25, 'completed')
ON DUPLICATE KEY UPDATE customer_id = VALUES(customer_id), order_date = VALUES(order_date), amount = VALUES(amount), status = VALUES(status);
