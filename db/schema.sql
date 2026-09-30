CREATE TABLE customers (
    customer_id     TEXT PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    country         TEXT NOT NULL,
    timezone        TEXT NOT NULL,
    signup_at       TIMESTAMPTZ NOT NULL,
    is_premium      BOOLEAN NOT NULL
);

CREATE TABLE subscriptions (
    subscription_id TEXT PRIMARY KEY,
    customer_id     TEXT NOT NULL REFERENCES customers(customer_id),
    plan            TEXT NOT NULL CHECK (plan IN ('pro_monthly', 'pro_annual')),
    channel         TEXT NOT NULL CHECK (channel IN ('web', 'apple', 'google')),
    started_at      TIMESTAMPTZ NOT NULL,
    ends_at         TIMESTAMPTZ
);

CREATE TABLE cancellations (
    cancellation_id TEXT PRIMARY KEY,
    subscription_id TEXT NOT NULL UNIQUE REFERENCES subscriptions(subscription_id),
    cancelled_at    TIMESTAMPTZ NOT NULL,
    reason          TEXT NOT NULL
);

CREATE TABLE payments (
    payment_id      TEXT PRIMARY KEY,
    invoice_id      TEXT NOT NULL,
    subscription_id TEXT NOT NULL REFERENCES subscriptions(subscription_id),
    customer_id     TEXT NOT NULL REFERENCES customers(customer_id),
    paid_at         TIMESTAMPTZ NOT NULL,
    amount_usd      NUMERIC(10, 2) NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('succeeded', 'failed'))
);

CREATE TABLE refunds (
    refund_id       TEXT PRIMARY KEY,
    payment_id      TEXT NOT NULL REFERENCES payments(payment_id),
    refunded_at     TIMESTAMPTZ NOT NULL,
    amount_usd      NUMERIC(10, 2) NOT NULL,
    reason          TEXT NOT NULL
);

CREATE TABLE store_transactions (
    transaction_id      TEXT PRIMARY KEY,
    subscription_id     TEXT NOT NULL REFERENCES subscriptions(subscription_id),
    customer_id         TEXT NOT NULL REFERENCES customers(customer_id),
    store               TEXT NOT NULL CHECK (store IN ('apple', 'google')),
    purchased_at        TIMESTAMPTZ NOT NULL,
    customer_price_usd  NUMERIC(10, 2) NOT NULL,
    proceeds_usd        NUMERIC(10, 2) NOT NULL
);

CREATE TABLE logins (
    login_id        BIGINT PRIMARY KEY,
    customer_id     TEXT NOT NULL REFERENCES customers(customer_id),
    logged_in_at    TIMESTAMPTZ NOT NULL,
    platform        TEXT NOT NULL CHECK (platform IN ('ios', 'android', 'web'))
);
