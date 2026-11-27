import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip,
  CartesianGrid, LineChart, Line,
} from 'recharts';
import './style.css';

const number = (value) =>
  new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 }).format(Number(value || 0));
const amount = (value) =>
  new Intl.NumberFormat('en-GB', { maximumFractionDigits: 2 }).format(Number(value || 0));

function App() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    fetch('/data/dashboard_data.json')
      .then((response) => {
        if (!response.ok) throw new Error('The refreshed 2025–2026 retail dataset is not available yet.');
        return response.json();
      })
      .then(setData)
      .catch((error) => setErr(error.message));
  }, []);

  if (!data) {
    return (
      <main className="shell">
        <header>
          <div className="brand">DQ<span> / </span>ANALYTICS</div>
          <span className="tag">PUBLIC DATA · AUDIT</span>
        </header>
        <section className="hero">
          <p className="eyebrow">REAL-DATA QUALITY REVIEW</p>
          <h1>Retail data quality<br />and performance.</h1>
          <p>{err || 'Loading analyzed dataset…'}</p>
          <div className="note">The dashboard only displays measured source data. No sample or date-shifted records are shown.</div>
        </section>
      </main>
    );
  }

  const k = data.kpis;
  const source = data.source;
  const kpiItems = [
    ['Clean sales records', number(k.clean_sales_rows)],
    ['Reported transactions', k.reported_transaction_count == null ? 'Not available' : number(k.reported_transaction_count)],
    ['Return records', number(k.return_rows)],
    ['Sales amount · source units', amount(k.sales_amount_total)],
    ['Stores', number(k.store_count)],
    ['Unique SKUs', number(k.sku_count)],
  ];

  return (
    <main className="shell">
      <header>
        <div className="brand">DQ<span> / </span>ANALYTICS</div>
        <span className="tag">MENDELEY RETAIL · 2025–2026</span>
      </header>

      <section className="hero">
        <p className="eyebrow">DATA QUALITY & BUSINESS INTELLIGENCE</p>
        <h1>Audit the data.<br />Understand the business.</h1>
        <p className="sub">
          Real sales and stock observations from {k.sales_start_date} to {k.sales_end_date}.
          Returns remain visible and are not silently treated as ordinary sales.
        </p>
        <div className="note">
          Latest inventory snapshot: {k.latest_inventory_date} · {number(k.latest_inventory_units)} units on hand across {number(k.inventory_store_count)} stores.
        </div>
      </section>

      <section className="grid kpis">
        {kpiItems.map(([label, val]) => (
          <article className="tile" key={label}>
            <p>{label}</p>
            <strong>{val}</strong>
          </article>
        ))}
      </section>

      <section className="grid charts">
        <article className="panel wide">
          <h2>Monthly sales amount · source units</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.monthly}>
              <CartesianGrid strokeDasharray="3 3" stroke="#283342" />
              <XAxis dataKey="month" stroke="#98a6b8" />
              <YAxis stroke="#98a6b8" />
              <Tooltip formatter={(value) => amount(value)} />
              <Line type="monotone" dataKey="sales" name="Sales amount" stroke="#60a5fa" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </article>

        <article className="panel">
          <h2>Sales by store · Top 12</h2>
          <ResponsiveContainer width="100%" height={360}>
            <BarChart data={data.stores} layout="vertical" margin={{ left: 15 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#283342" />
              <XAxis type="number" stroke="#98a6b8" />
              <YAxis type="category" dataKey="store_id" width={105} stroke="#98a6b8" />
              <Tooltip formatter={(value) => amount(value)} />
              <Bar dataKey="sales" name="Sales amount" fill="#34d399" />
            </BarChart>
          </ResponsiveContainer>
        </article>

        <article className="panel">
          <h2>Top products by sales amount</h2>
          <div className="tablewrap">
            <table>
              <thead><tr><th>Product</th><th>Units</th><th>Sales</th></tr></thead>
              <tbody>
                {data.products.map((product, index) => (
                  <tr key={String(product.sku_id) + '-' + index}>
                    <td>{String(product.product_description || product.sku_id).slice(0, 42)}</td>
                    <td>{number(product.units)}</td>
                    <td>{amount(product.sales)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel">
          <h2>Sales by channel</h2>
          <div className="tablewrap">
            <table>
              <thead><tr><th>Channel</th><th>Rows</th><th>Sales</th></tr></thead>
              <tbody>
                {data.channels.map((channel, index) => (
                  <tr key={String(channel.sales_channel) + '-' + index}>
                    <td>{channel.sales_channel || 'Unspecified'}</td>
                    <td>{number(channel.rows)}</td>
                    <td>{amount(channel.sales)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel">
          <h2>Source verification</h2>
          <p className="sub">Publisher: {source.publisher}</p>
          <p className="sub">DOI: {source.dataset_doi}</p>
          <p className="sub">Licence: {source.license}</p>
          <p className="sub">Sales rows checked: {number(source.sales_observed_rows)}</p>
          <p className="sub">Inventory rows checked: {number(source.inventory_observed_rows)}</p>
          <p className="sub">The reported date range is measured from the CSV transaction and stock-start date fields.</p>
        </article>
      </section>

      <section className="panel">
        <h2>Quality audit findings</h2>
        <div className="tablewrap">
          <table>
            <thead><tr><th>Field / Rule</th><th>Type</th><th>Missing</th><th>Missing %</th><th>Distinct / flags</th></tr></thead>
            <tbody>
              {data.audit.map((audit, index) => (
                <tr key={String(audit.field) + '-' + index}>
                  <td>{audit.field}</td>
                  <td>{audit.dtype}</td>
                  <td>{number(audit.missing_count)}</td>
                  <td>{audit.missing_pct}%</td>
                  <td>{number(audit.distinct_values)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <footer>
        Source: {source.attribution} · Dataset licence: {source.license}. This dashboard reports the measured source period and does not create synthetic 2025/2026 transactions.
      </footer>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
