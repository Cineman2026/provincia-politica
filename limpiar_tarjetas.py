"""
LIMPIAR TARJETAS R2 — PROVINCIA POLÍTICA
=========================================
Borra del bucket de Cloudflare R2 las tarjetas con más de DIAS_RETENCION días
de antigüedad (según su fecha de subida / LastModified).

Corre 1 vez por día via GitHub Actions. Mantiene el bucket liviano sin
intervención manual.
"""

import os
import sys
from datetime import datetime, timezone, timedelta

import boto3

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DIAS_RETENCION = 10

CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID")
CF_R2_ACCESS_KEY = os.environ.get("CF_R2_ACCESS_KEY_ID")
CF_R2_SECRET_KEY = os.environ.get("CF_R2_SECRET_ACCESS_KEY")
CF_R2_BUCKET = os.environ.get("CF_R2_BUCKET_NAME")


def main():
    if not (CF_ACCOUNT_ID and CF_R2_ACCESS_KEY and CF_R2_SECRET_KEY and CF_R2_BUCKET):
        print("❌ Faltan credenciales de Cloudflare R2")
        sys.exit(1)

    endpoint = "https://{}.r2.cloudflarestorage.com".format(CF_ACCOUNT_ID)
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=CF_R2_ACCESS_KEY,
        aws_secret_access_key=CF_R2_SECRET_KEY,
        region_name="auto",
    )

    limite = datetime.now(timezone.utc) - timedelta(days=DIAS_RETENCION)
    print("=" * 52)
    print("  LIMPIEZA DE TARJETAS R2 — PROVINCIA POLÍTICA")
    print("  Borra tarjetas subidas antes de: {}".format(limite.strftime("%Y-%m-%d %H:%M UTC")))
    print("=" * 52)

    borradas = 0
    conservadas = 0
    errores = 0

    # Paginar por si hay muchos objetos
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=CF_R2_BUCKET):
        objetos = page.get("Contents", [])
        for obj in objetos:
            key = obj["Key"]
            last_modified = obj["LastModified"]  # datetime con tz
            if last_modified < limite:
                try:
                    s3.delete_object(Bucket=CF_R2_BUCKET, Key=key)
                    edad_dias = (datetime.now(timezone.utc) - last_modified).days
                    print("  🗑️  Borrada: {} ({} días)".format(key, edad_dias))
                    borradas += 1
                except Exception as e:
                    print("  ⚠️  Error borrando {}: {}".format(key, str(e)[:80]))
                    errores += 1
            else:
                conservadas += 1

    print("-" * 52)
    print("✨ Listo. {} borrada(s), {} conservada(s), {} error(es).".format(
        borradas, conservadas, errores))


if __name__ == "__main__":
    main()
