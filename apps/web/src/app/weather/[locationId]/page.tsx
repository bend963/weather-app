import { Dashboard } from "@/components/Dashboard";

export default async function WeatherPage({ params }: { params: Promise<{ locationId: string }> }) {
  const { locationId } = await params;
  return <Dashboard locationId={locationId} />;
}
