from pathlib import Path
import hashlib, json, zipfile, sqlite3, sys
import requests
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; REPORTS=ROOT/'reports'; RAW=DATA/'raw'; REPORTS.mkdir(parents=True,exist_ok=True); RAW.mkdir(parents=True,exist_ok=True)
URL='https://archive.ics.uci.edu/static/public/352/online+retail.zip'
EXPECTED_ROWS=541909
EXPECTED_COLS=['InvoiceNo','StockCode','Description','Quantity','InvoiceDate','UnitPrice','CustomerID','Country']

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def main():
    archive=RAW/'online_retail_uci.zip'
    print('Downloading original dataset from UCI...')
    with requests.get(URL,stream=True,timeout=120) as r:
        r.raise_for_status()
        with open(archive,'wb') as f:
            for chunk in r.iter_content(1024*1024):
                if chunk: f.write(chunk)
    print('Archive bytes:',archive.stat().st_size)
    print('SHA-256:',sha256(archive))
    with zipfile.ZipFile(archive) as z:
        candidates=[n for n in z.namelist() if n.lower().endswith('.xlsx')]
        if not candidates: raise RuntimeError('ZIP contains no Excel file. Inspect source archive.')
        source=RAW/'Online Retail.xlsx'
        with z.open(candidates[0]) as src, open(source,'wb') as dst:
            dst.write(src.read())
    df=pd.read_excel(source)
    actual_cols=list(df.columns)
    cols_ok=actual_cols==EXPECTED_COLS
    verification={
        'dataset':'UCI Online Retail','official_source_url':'https://archive.ics.uci.edu/dataset/352/online+retail',
        'download_url':URL,'citation':'Chen, D. (2015). Online Retail. UCI Machine Learning Repository. DOI: 10.24432/C5BW33. CC BY 4.0.',
        'archive_filename':archive.name,'archive_bytes':archive.stat().st_size,'archive_sha256':sha256(archive),
        'workbook_filename':source.name,'observed_rows':len(df),'expected_rows_reference':EXPECTED_ROWS,
        'row_count_matches_reference':len(df)==EXPECTED_ROWS,'observed_columns':actual_cols,
        'expected_columns':EXPECTED_COLS,'columns_match_reference':cols_ok,
        'source_provenance_note':'UCI repository documentation is the provenance reference. Hash checks file integrity, not truth of underlying records.'}
    (REPORTS/'source_verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
    required=[c for c in EXPECTED_COLS if c not in df.columns]
    if required: raise ValueError('Missing required fields: '+', '.join(required))
    # Normalize data types while preserving original source file.
    df['InvoiceDate']=pd.to_datetime(df['InvoiceDate'],errors='coerce')
    df['Quantity']=pd.to_numeric(df['Quantity'],errors='coerce')
    df['UnitPrice']=pd.to_numeric(df['UnitPrice'],errors='coerce')
    df['CustomerID']=pd.to_numeric(df['CustomerID'],errors='coerce')
    duplicates=int(df.duplicated().sum())
    audit=[]
    for col in df.columns:
        audit.append({'field':col,'dtype':str(df[col].dtype),'missing_count':int(df[col].isna().sum()),'missing_pct':round(float(df[col].isna().mean()*100),2),'distinct_values':int(df[col].nunique(dropna=True))})
    audit.extend([
      {'field':'__exact_duplicate_rows__','dtype':'rule','missing_count':0,'missing_pct':0,'distinct_values':duplicates},
      {'field':'__quantity_le_zero__','dtype':'rule','missing_count':0,'missing_pct':0,'distinct_values':int((df['Quantity']<=0).sum())},
      {'field':'__unitprice_le_zero__','dtype':'rule','missing_count':0,'missing_pct':0,'distinct_values':int((df['UnitPrice']<=0).sum())},
      {'field':'__cancellation_invoice__','dtype':'rule','missing_count':0,'missing_pct':0,'distinct_values':int(df['InvoiceNo'].astype(str).str.startswith('C',na=False).sum())},
    ])
    pd.DataFrame(audit).to_csv(REPORTS/'data_quality_audit.csv',index=False)
    # Clean working copy: deduplicate and remove invalid transaction rows for positive-sales analysis.
    dedup=df.drop_duplicates().copy()
    valid=dedup[(dedup['Quantity']>0)& (dedup['UnitPrice']>0)&dedup['InvoiceDate'].notna()].copy()
    valid['Revenue']=valid['Quantity']*valid['UnitPrice']
    valid['InvoiceMonth']=valid['InvoiceDate'].dt.to_period('M').astype(str)
    cancelled=df['InvoiceNo'].astype(str).str.startswith('C',na=False)
    gross_rows=dedup[~dedup['InvoiceNo'].astype(str).str.startswith('C',na=False)]
    cancel_rows=dedup[dedup['InvoiceNo'].astype(str).str.startswith('C',na=False)]
    # dashboard metrics calculated from cleaned positive sales, cancellation counts kept as separate source KPI
    month=valid.groupby('InvoiceMonth').agg(transaction_rows=('InvoiceNo','size'),revenue=('Revenue','sum')).reset_index()
    country=valid.groupby('Country').agg(rows=('InvoiceNo','size'),revenue=('Revenue','sum')).reset_index().sort_values('revenue',ascending=False).head(12)
    products=valid.groupby(['StockCode','Description'],dropna=False).agg(units=('Quantity','sum'),revenue=('Revenue','sum')).reset_index().sort_values('revenue',ascending=False).head(12)
    kpis={'source_rows':int(len(df)),'exact_duplicates':duplicates,'missing_customer_id_rows':int(df['CustomerID'].isna().sum()),
          'cancellation_invoice_rows':int(cancelled.sum()),'nonpositive_quantity_rows':int((df['Quantity']<=0).sum()),
          'nonpositive_unit_price_rows':int((df['UnitPrice']<=0).sum()),'clean_positive_sale_rows':int(len(valid)),
          'clean_positive_sales_revenue_gbp':round(float(valid['Revenue'].sum()),2),
          'countries':int(valid['Country'].nunique()),'unique_customers_with_id':int(valid['CustomerID'].nunique()),
          'source_start_date':str(df['InvoiceDate'].min()),'source_end_date':str(df['InvoiceDate'].max()),
          'cleaning_policy':'Exact duplicates removed; positive quantity/price and valid dates included in positive-sales analysis. Missing customer IDs retained for sales analysis.'}
    (REPORTS/'kpis.json').write_text(json.dumps(kpis,indent=2),encoding='utf-8')
    dashboard={'kpis':kpis,'monthly':month.to_dict(orient='records'),'countries':country.to_dict(orient='records'),'products':products.to_dict(orient='records'),'audit':audit}
    (REPORTS/'dashboard_data.json').write_text(json.dumps(dashboard,indent=2,default=str),encoding='utf-8')
    dash_data=ROOT/'dashboard'/'public'/'data'/'dashboard_data.json'
    dash_data.parent.mkdir(parents=True,exist_ok=True)
    dash_data.write_text(json.dumps(dashboard,indent=2,default=str),encoding='utf-8')
    valid.to_csv(REPORTS/'clean_transactions.csv',index=False)
    # SQLite with raw-ish cleaned table, plus useful query examples
    db=REPORTS/'analysis.sqlite'
    with sqlite3.connect(db) as con:
        valid.to_sql('clean_transactions',con,if_exists='replace',index=False)
        con.execute('CREATE INDEX IF NOT EXISTS idx_month ON clean_transactions(InvoiceMonth)')
    print('\nPipeline complete. Outputs saved under reports/.')
    print(json.dumps(kpis,indent=2))
    print('Dataset columns match expected:',cols_ok)
    print('Row count matches reference:',len(df)==EXPECTED_ROWS)
if __name__=='__main__': main()
