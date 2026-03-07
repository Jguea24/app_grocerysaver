from .models import ProductCode, ProductCodeType


class RequestDataLoader:
    def __init__(self, batch_load_fn):
        self.batch_load_fn = batch_load_fn
        self.cache = {}

    def load_many(self, keys):
        normalized_keys = []
        seen = set()
        for key in keys:
            if key is None or key in seen:
                continue
            seen.add(key)
            normalized_keys.append(key)

        missing_keys = [key for key in normalized_keys if key not in self.cache]
        if missing_keys:
            batch_data = self.batch_load_fn(missing_keys) or {}
            for key in missing_keys:
                self.cache[key] = batch_data.get(key)

        return {key: self.cache.get(key) for key in normalized_keys}

    def load(self, key, batch_keys=None):
        if key is None:
            return None

        self.load_many(batch_keys or [key])
        return self.cache.get(key)


def get_request_loader(request, name, batch_load_fn):
    if request is None:
        return RequestDataLoader(batch_load_fn)

    loaders = getattr(request, '_grocerysaver_dataloaders', None)
    if loaders is None:
        loaders = {}
        setattr(request, '_grocerysaver_dataloaders', loaders)

    loader = loaders.get(name)
    if loader is None:
        loader = RequestDataLoader(batch_load_fn)
        loaders[name] = loader

    return loader


def batch_load_product_qr_codes(product_ids):
    qr_codes_by_product_id = {product_id: None for product_id in product_ids}
    qr_rows = (
        ProductCode.objects.filter(product_id__in=product_ids, code_type=ProductCodeType.QR)
        .order_by('product_id', 'created_at')
        .values('product_id', 'code')
    )

    for qr_row in qr_rows:
        product_id = qr_row['product_id']
        if qr_codes_by_product_id.get(product_id) is None:
            qr_codes_by_product_id[product_id] = qr_row['code']

    return qr_codes_by_product_id
