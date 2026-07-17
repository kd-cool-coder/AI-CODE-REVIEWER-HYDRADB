def process_order(order):
    if order.is_valid():
        if order.has_inventory():
            if order.payment_cleared():
                return fulfill(order)
            else:
                return {"error": "payment failed"}
        else:
            return {"error": "out of stock"}
    else:
        return {"error": "invalid order"}


def parse_retry_count(payload):
    try:
        return int(payload.get("retry_count", 0))
    except:
        return 0


def fulfill(order):
    return {
        "status": "fulfilled",
        "order_id": order.id,
    }
