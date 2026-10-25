"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Point = { name: string; reliability: number; agreement: number };

export default function CandidateChart({ data }: { data: Point[] }) {
  return <div className="mt-4 h-64 w-full"><ResponsiveContainer width="100%" height="100%"><BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -22 }}><CartesianGrid stroke="#ffffff0b" vertical={false}/><XAxis dataKey="name" tick={{ fill: "#777b86", fontSize: 10 }} axisLine={false} tickLine={false}/><YAxis domain={[0,100]} tick={{ fill: "#777b86", fontSize: 9 }} axisLine={false} tickLine={false}/><Tooltip contentStyle={{ background: "#171920", border: "1px solid #30323b", borderRadius: 10, fontSize: 11 }} cursor={{ fill: "#ffffff08" }}/><Bar dataKey="reliability" name="Reliability" fill="#ab92ed" radius={[5,5,0,0]}/><Bar dataKey="agreement" name="Agreement" fill="#69c4ce" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer></div>;
}
