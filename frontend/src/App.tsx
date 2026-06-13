import { Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/AppShell";
import { OverviewPage } from "@/pages/OverviewPage";
import { GraphPage } from "@/pages/GraphPage";
import { FindingsPage } from "@/pages/FindingsPage";
import { StatisticsPage } from "@/pages/StatisticsPage";
import { ProfilePage } from "@/pages/ProfilePage";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="graph" element={<GraphPage />} />
        <Route path="findings" element={<FindingsPage />} />
        <Route path="statistics" element={<StatisticsPage />} />
        <Route path="profile" element={<ProfilePage />} />
      </Route>
    </Routes>
  );
}
