
import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  LineChart,
  Line,
} from 'recharts';
import './style.css';

function App() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    fetch('/data/dashboard_data.json')
      .then((response) => {
        if (!response.ok) {
          throw new Error(
            'Run the Python pipeline first to create dashboard data.'
          );
        }
        return response.json();
      })
      .then(setData)
      .catch((error) => setErr(error.message));
  }, []);

  if (!data) {
    return (
      <main className="shell">
        <header>
          <div className="brand">
            DQ<span> / </span>ANALYTICS
          </div>
          <span className="tag">PUBLIC DATA · AUDIT</span>
        </header>

        <section className="hero">
          <p className="eyebrow">REAL-DATA QUALITY REVIEW</p>
          <h1>
            Retail data quality
            <br />
            and performance.
          </h1>
          <p>{err || 'Loading analyzed dataset…'}</p>
          <div className="note">
            Run the automated dataset pipeline to populate metrics.
            No sample metrics are displayed.
          </div>
        </section>
      </main>
    );
  }

  const k = data.kpis;

  const fmt = (number) =>
    new Intl.NumberFormat('en-GB').format(number || 0);

  const kpiItems = [
    ['Source records', fmt(k.source_rows)],
    ['Exact duplicates', fmt(k.exact_duplicates)],
    ['Missing Customer IDs', fmt(k.missing_customer_id_rows)],
    ['Cancellation invoices', fmt(k.cancellation_invoice_rows)],
    ['Clean sales rows', fmt(k.clean_positive_sale_rows)],
    [
      'Clean sales revenue',
      `£${fmt(k.clean_positive_sales_revenue_gbp)}`,
    ],
  ];

  return (
    <main className="shell">
      <header>
        <div className="brand">
          DQ<span> / </span>ANALYTICS
        </div>
        <span className="tag">UCI ONLINE RETAIL · REAL DATA</span>
      </header>

      <section className="hero">
        <p className="eyebrow">DATA QUALITY & BUSINESS INTELLIGENCE</p>
        <h1>
          Audit the data.
          <br />
          Understand the business.
        </h1>
        <p className="sub">
          Evidence-led analysis of documented historical retail transactions.
        </p>
      </section>

      {/* KPI Cards */}
      <section className="grid kpis">
        {kpiItems.map(([label, val]) => (
          <article className="tile" key={label}>
            <p>{label}</p>
            <strong>{val}</strong>
          </article>
        ))}
      </section>

      {/* Charts */}
      <section className="grid charts">
        <article className="panel wide">
          <h2>Monthly retail revenue</h2>

          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.monthly}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#283342"
              />
              <XAxis
                dataKey="InvoiceMonth"
                stroke="#98a6b8"
              />
              <YAxis stroke="#98a6b8" />
              <Tooltip />

              <Line
                type="monotone"
                dataKey="revenue"
                stroke="#60a5fa"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </article>

        <article className="panel">
          <h2>Revenue by country · Top 12</h2>

          <ResponsiveContainer width="100%" height={360}>
            <BarChart
              data={data.countries}
              layout="vertical"
              margin={{ left: 15 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#283342"
              />
              <XAxis
                type="number"
                stroke="#98a6b8"
              />
              <YAxis
                type="category"
                dataKey="Country"
                width={105}
                stroke="#98a6b8"
              />
              <Tooltip />
              <Bar
                dataKey="revenue"
                fill="#34d399"
              />
            </BarChart>
          </ResponsiveContainer>
        </article>

        <article className="panel">
          <h2>Top products by revenue</h2>

          <div className="tablewrap">
            <table>
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Units</th>
                  <th>Revenue</th>
                </tr>
              </thead>

              <tbody>
                {data.products.map((product, index) => (
                  <tr key={index}>
                    <td>
                      {String(
                        product.Description || product.StockCode
                      ).slice(0, 42)}
                    </td>
                    <td>{fmt(product.units)}</td>
                    <td>£{fmt(product.revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>

      {/* Data quality audit */}
      <section className="panel">
        <h2>Quality audit findings</h2>

        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>Field / Rule</th>
                <th>Type</th>
                <th>Missing</th>
                <th>Missing %</th>
                <th>Distinct / flags</th>
              </tr>
            </thead>

            <tbody>
              {data.audit.map((audit) => (
                <tr key={audit.field}>
                  <td>{audit.field}</td>
                  <td>{audit.dtype}</td>
                  <td>{fmt(audit.missing_count)}</td>
                  <td>{audit.missing_pct}%</td>
                  <td>{fmt(audit.distinct_values)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <footer>
        Source: UCI Online Retail · Dataset is documented public historical
        data, not independently audited. Metrics generated from downloaded
        file by local pipeline.
      </footer>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
