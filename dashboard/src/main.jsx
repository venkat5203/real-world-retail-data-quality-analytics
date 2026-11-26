import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, LineChart, Line } from 'recharts';
import './style.css';

function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch('/data/dashboard_data.json')
      .then((response) => {
        if (!response.ok) throw new Error('Run python src/pipeline.py to create the 2026 catalogue snapshot.');
        return response.json();
      })
      .then((payload) => {
        if (payload.status !== 'ready') throw new Error(payload.message || 'Refresh the 2026 product catalogue first.');
        setData(payload);
      })
      .catch((err) => setError(err.message));
  }, []);

  if (!data) {
    return (
      <main className="shell">
        <header>
          <div className="brand">DQ<span> / </span>ANALYTICS</div>
          <span className="tag">2026 PRODUCT CATALOGUE</span>
        </header>
        <section className="hero">
          <p className="eyebrow">CURRENT-DATA QUALITY REVIEW</p>
          <h1>Audit the catalogue.<br />Trust the attributes.</h1>
          <p>{error || 'Loading the latest available snapshot…'}</p>
          <div className="note">No legacy 2010–2011 transaction metrics are shown. Run the updated Python pipeline to generate the current product snapshot.</div>
        </section>
      </main>
    );
  }

  const k = data.kpis;
  const fmt = (n) => new Intl.NumberFormat('en-GB').format(n || 0);
  const dateOnly = (v) => v ? new Date(v).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }) : '—';
  const cards = [
    ['Products audited', fmt(k.products_in_snapshot)],
    ['Avg. selected-field completeness', fmt(k.average_selected_field_completeness_pct) + '%'],
    ['Missing brands', fmt(k.missing_brand_rows)],
    ['Missing categories', fmt(k.missing_category_rows)],
    ['Missing nutrition records', fmt(k.missing_nutrition_rows)],
    ['Invalid nutrient records', fmt(k.invalid_nutrient_rows)],
  ];

  return (
    <main className="shell">
      <header>
        <div className="brand">DQ<span> / </span>ANALYTICS</div>
        <span className="tag">OPEN FOOD FACTS · 2026 SNAPSHOT</span>
      </header>
      <section className="hero">
        <p className="eyebrow">PRODUCT DATA QUALITY & BUSINESS INTELLIGENCE</p>
        <h1>Audit the catalogue.<br />Trust the attributes.</h1>
        <p className="sub">A reproducible quality audit of product records recently updated in 2026.</p>
        <div className="note">Snapshot collected {dateOnly(data.metadata.retrieved_at_utc)} · Product update window: {dateOnly(data.metadata.last_modified_window_utc.from)} to {dateOnly(data.metadata.last_modified_window_utc.to)}.</div>
      </section>
      <section className="grid kpis">
        {cards.map(([label, value]) => (
          <article className="tile" key={label}><p>{label}</p><strong>{value}</strong></article>
        ))}
      </section>
      <section className="grid charts">
        <article className="panel wide">
          <h2>Product records updated by month · 2026</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.monthly_updates}>
              <CartesianGrid strokeDasharray="3 3" stroke="#283342" />
              <XAxis dataKey="month" stroke="#98a6b8" /><YAxis stroke="#98a6b8" /><Tooltip />
              <Line type="monotone" dataKey="products_updated" stroke="#60a5fa" strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
        </article>
        <article className="panel">
          <h2>Top product categories</h2>
          <ResponsiveContainer width="100%" height={360}>
            <BarChart data={data.categories} layout="vertical" margin={{ left: 12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#283342" /><XAxis type="number" stroke="#98a6b8" />
              <YAxis type="category" dataKey="category" width={145} stroke="#98a6b8" /><Tooltip />
              <Bar dataKey="product_count" fill="#34d399" />
            </BarChart>
          </ResponsiveContainer>
        </article>
        <article className="panel">
          <h2>Top brands in snapshot</h2>
          <div className="tablewrap">
            <table><thead><tr><th>Brand</th><th>Products</th></tr></thead>
              <tbody>{data.brands.map((brand) => <tr key={brand.brand}><td>{brand.brand}</td><td>{fmt(brand.product_count)}</td></tr>)}</tbody>
            </table>
          </div>
        </article>
      </section>
      <section className="panel">
        <h2>Recently updated products</h2>
        <div className="tablewrap">
          <table><thead><tr><th>Product</th><th>Brand</th><th>Category</th><th>Completeness</th><th>Last modified (UTC)</th></tr></thead>
            <tbody>{data.products.map((product) => (
              <tr key={product.barcode}>
                <td>{product.product_name || 'Unnamed product'} <span className="muted">({product.barcode})</span></td>
                <td>{product.primary_brand || '—'}</td><td>{product.primary_category}</td>
                <td>{product.completeness_pct}%</td><td>{dateOnly(product.last_modified_at_utc)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </section>
      <section className="panel">
        <h2>Quality audit findings</h2>
        <div className="tablewrap">
          <table><thead><tr><th>Field / Rule</th><th>Flagged records</th><th>Flagged %</th><th>Distinct / valid count</th></tr></thead>
            <tbody>{data.audit.map((row) => <tr key={row.rule}><td>{row.field}</td><td>{fmt(row.flagged_count)}</td><td>{row.flagged_pct}%</td><td>{fmt(row.distinct_values)}</td></tr>)}</tbody>
          </table>
        </div>
      </section>
      <footer>Source: <a href={data.metadata.source_url} target="_blank" rel="noreferrer">Open Food Facts</a> · Attribution: {data.metadata.attribution} · Licence: {data.metadata.license}. This is product catalogue data, not sales or customer purchase history.</footer>
    </main>
  );
}
createRoot(document.getElementById('root')).render(<App />);
