import React from "react";
import { ClassAnalytics, TrendLabel } from "../types/synapse";
import { Card } from "./UI";

export interface AnalyticsChartsProps {
  analytics: ClassAnalytics;
}

export const AnalyticsCharts: React.FC<AnalyticsChartsProps> = ({ analytics }) => {
  const trendEntries = Object.entries(analytics.trend_distribution || {}) as [TrendLabel, number][];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <div className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Class Size</div>
          <div className="text-3xl font-bold text-slate-100 mt-2">{analytics.student_count}</div>
          <div className="text-xs text-slate-500 mt-1">Students assessed</div>
        </Card>

        <Card>
          <div className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Average Mastery</div>
          <div className="text-3xl font-bold text-sky-400 mt-2">
            {Math.round(analytics.average_mastery * 100)}%
          </div>
          <div className="text-xs text-slate-500 mt-1">Benchmark threshold: 50%</div>
        </Card>

        <Card>
          <div className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Attention Required</div>
          <div className="text-3xl font-bold text-rose-400 mt-2">{analytics.weak_students.length}</div>
          <div className="text-xs text-slate-500 mt-1">Students below 50% mastery</div>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Student Learning Trends">
          <div className="space-y-3">
            {trendEntries.map(([trend, count]) => {
              const pct = analytics.student_count > 0 ? Math.round((count / analytics.student_count) * 100) : 0;
              const colorClass = {
                improving: "bg-emerald-500",
                stable: "bg-sky-500",
                still_weak: "bg-amber-500",
                declining: "bg-rose-500",
                new: "bg-purple-500",
              }[trend] || "bg-slate-500";

              return (
                <div key={trend} className="space-y-1">
                  <div className="flex justify-between text-xs text-slate-300">
                    <span className="capitalize font-medium">{trend.replace("_", " ")}</span>
                    <span>{count} students ({pct}%)</span>
                  </div>
                  <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                    <div className={`h-full ${colorClass}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <Card title="Intervention List (Anonymous IDs)">
          {analytics.weak_students.length === 0 ? (
            <div className="text-sm text-emerald-400 py-4">All students are currently at or above mastery threshold.</div>
          ) : (
            <div className="space-y-2">
              <p className="text-xs text-slate-400 mb-2">
                Students below 50% mastery on {analytics.concept_name}:
              </p>
              <div className="flex flex-wrap gap-2">
                {analytics.weak_students.map((sid) => (
                  <span
                    key={sid}
                    className="px-2.5 py-1 bg-rose-950/60 border border-rose-800 text-rose-300 rounded text-xs font-mono"
                  >
                    {sid}
                  </span>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};
