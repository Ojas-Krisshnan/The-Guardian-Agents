import React from "react";
import { AnalyticsCharts } from "../../components/AnalyticsCharts";
import { Card, Loading } from "../../components/UI";
import { useAnalytics } from "../../hooks";

export interface AnalyticsPageProps {
  conceptId: string;
}

export const AnalyticsPage: React.FC<AnalyticsPageProps> = ({ conceptId }) => {
  const { analytics, loading, error } = useAnalytics(conceptId);

  if (loading) return <Loading message="Loading class performance analytics..." />;

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Class Performance & Trend Analytics</h1>
          <p className="text-sm text-slate-400 mt-1">
            Aggregate diagnostic telemetry across student attempts for concept <strong>{conceptId}</strong>.
          </p>
        </div>
        <span className="text-xs bg-slate-800 text-slate-400 px-3 py-1.5 rounded-lg border border-slate-700">
          Teacher Telemetry View
        </span>
      </div>

      {error && (
        <div className="p-4 bg-rose-950/40 border border-rose-800 rounded-xl text-rose-300 text-sm">
          {error}
        </div>
      )}

      {analytics ? (
        <AnalyticsCharts analytics={analytics} />
      ) : (
        <Card>
          <div className="text-center py-8 text-slate-400 text-sm">
            No diagnostic analytics currently aggregated for this concept.
          </div>
        </Card>
      )}
    </div>
  );
};
