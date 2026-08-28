import os
import psycopg2
from psycopg2.extras import RealDictCursor


DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL не установлен")

    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance NUMERIC(12, 2) NOT NULL DEFAULT 0,
            referrals INTEGER NOT NULL DEFAULT 0,
            invited_by BIGINT,
            roulette_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS promo_uses (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            promo_code TEXT NOT NULL,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, promo_code)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY,
            reward NUMERIC(12, 2) NOT NULL,
            max_uses INTEGER NOT NULL,
            uses INTEGER NOT NULL DEFAULT 0,
            active BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            amount NUMERIC(12, 2) NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS roulette_uses (
            user_id BIGINT NOT NULL,
            play_date DATE NOT NULL,
            reward NUMERIC(12, 2) NOT NULL,
            PRIMARY KEY(user_id, play_date)
        )
    """)

    cur.execute("""
        INSERT INTO promos
            (code, reward, max_uses)
        VALUES
            ('IZIDROP', 12, 100),
            ('LOL10', 10, 10)
        ON CONFLICT (code) DO NOTHING
    """)

    conn.commit()

    cur.close()
    conn.close()


def create_user(
    user_id,
    username=None,
    first_name=None,
    invited_by=None
):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users
            (
                user_id,
                username,
                first_name,
                balance,
                referrals,
                invited_by
            )
        VALUES
            (%s, %s, %s, 0, 0, %s)
        ON CONFLICT (user_id) DO NOTHING
    """, (
        user_id,
        username,
        first_name,
        invited_by
    ))

    conn.commit()

    cur.close()
    conn.close()


def get_user(user_id):
    conn = get_connection()

    cur = conn.cursor(
        cursor_factory=RealDictCursor
    )

    cur.execute("""
        SELECT *
        FROM users
        WHERE user_id = %s
    """, (user_id,))

    user = cur.fetchone()

    cur.close()
    conn.close()

    return user


def add_balance(user_id, amount):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance = balance + %s
        WHERE user_id = %s
    """, (
        amount,
        user_id
    ))

    success = cur.rowcount == 1

    conn.commit()

    cur.close()
    conn.close()

    return success


def remove_balance(user_id, amount):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance = balance - %s
        WHERE user_id = %s
          AND balance >= %s
    """, (
        amount,
        user_id,
        amount
    ))

    success = cur.rowcount == 1

    conn.commit()

    cur.close()
    conn.close()

    return success


def process_referral(
    inviter_id,
    invited_user_id,
    reward=0.85
):
    """
    Начисляет +0.85 ⭐ пригласившему
    только один раз за одного приглашённого.
    """

    if inviter_id == invited_user_id:
        return False

    conn = get_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT invited_by
            FROM users
            WHERE user_id = %s
            FOR UPDATE
        """, (
            invited_user_id,
        ))

        invited = cur.fetchone()

        if not invited:
            return False

        if invited[0] is not None:
            return False

        cur.execute("""
            SELECT user_id
            FROM users
            WHERE user_id = %s
        """, (
            inviter_id,
        ))

        if not cur.fetchone():
            return False

        cur.execute("""
            UPDATE users
            SET invited_by = %s
            WHERE user_id = %s
              AND invited_by IS NULL
        """, (
            inviter_id,
            invited_user_id
        ))

        if cur.rowcount != 1:
            conn.rollback()
            return False

        cur.execute("""
            UPDATE users
            SET
                balance = balance + %s,
                referrals = referrals + 1
            WHERE user_id = %s
        """, (
            reward,
            inviter_id
        ))

        conn.commit()

        return True

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


def add_referral(inviter_id, reward=0.85):
    """
    Старый метод оставлен для совместимости.
    """

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET
            referrals = referrals + 1,
            balance = balance + %s
        WHERE user_id = %s
    """, (
        reward,
        inviter_id
    ))

    success = cur.rowcount == 1

    conn.commit()

    cur.close()
    conn.close()

    return success


# ==========================================
# ВЫВОД STARS
# ==========================================

def create_withdrawal(user_id, amount):
    """
    Создаёт заявку на вывод.

    Минимум: 15 ⭐
    Максимум: 10 000 ⭐

    Сумма списывается с баланса
    только если средств достаточно.
    """

    amount = float(amount)

    if amount < 15:
        return {
            "success": False,
            "error": "Минимальная сумма вывода — 15 ⭐"
        }

    if amount > 10000:
        return {
            "success": False,
            "error": "Максимальная сумма вывода — 10 000 ⭐"
        }

    conn = get_connection()
    cur = conn.cursor()

    try:

        # Атомарно списываем баланс
        cur.execute("""
            UPDATE users
            SET balance = balance - %s
            WHERE user_id = %s
              AND balance >= %s
        """, (
            amount,
            user_id,
            amount
        ))

        if cur.rowcount != 1:

            conn.rollback()

            return {
                "success": False,
                "error": "Недостаточно Stars на балансе"
            }

        # Создаём заявку
        cur.execute("""
            INSERT INTO withdrawals
                (
                    user_id,
                    amount,
                    status
                )
            VALUES
                (
                    %s,
                    %s,
                    'pending'
                )
            RETURNING id
        """, (
            user_id,
            amount
        ))

        withdrawal_id = cur.fetchone()[0]

        conn.commit()

        return {
            "success": True,
            "withdrawal_id": withdrawal_id,
            "amount": amount
        }

    except Exception:

        conn.rollback()
        raise

    finally:

        cur.close()
        conn.close()
