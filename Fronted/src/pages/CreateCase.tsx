import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

const initialForm = {
  company: "", department: "", category: "Customer", external_contact: "",
  responsible_person: "", status: "New", risk: "Low", description: "",
  next_action: "", primary_deadline: "", follow_up_date: "",
};

export default function CreateCase() {
  const navigate = useNavigate();
  const [form, setForm] = useState(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function handleChange(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setSubmitting(true); setError("");
      const response = await api.post("/cases/", {
        company: form.company.trim(), department: form.department.trim() || null,
        category: form.category, external_contact: form.external_contact.trim() || null,
        responsible_person: form.responsible_person.trim() || null, status: form.status,
        risk: form.risk, description: form.description.trim() || null,
        next_action: form.next_action.trim() || null,
        primary_deadline: form.primary_deadline || null, follow_up_date: form.follow_up_date || null,
      });
      navigate(`/cases/${response.data.id}`, { replace: true });
    } catch (requestError: any) {
      const detail = requestError.response?.data?.detail;
      setError(typeof detail === "string" ? detail : Array.isArray(detail)
        ? detail.map((item: any) => item.msg).join("; ") : "The case could not be created.");
    } finally { setSubmitting(false); }
  }

  return <div className="mx-auto max-w-5xl p-8">
    <header className="mb-8"><h1 className="text-3xl font-bold text-slate-950">Create case</h1>
      <p className="mt-2 text-sm text-slate-500">Enter the case information, responsibility, risk and next action.</p></header>
    {error && <div className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>}
    <form onSubmit={handleSubmit} className="grid gap-5 rounded-2xl border border-slate-200 bg-white p-7 shadow-sm md:grid-cols-2">
      <Field label="Company"><input name="company" value={form.company} onChange={handleChange} required className="input" /></Field>
      <Field label="Department"><input name="department" value={form.department} onChange={handleChange} className="input" /></Field>
      <Field label="Category"><select name="category" value={form.category} onChange={handleChange} className="input">{["Customer","Contract","Supplier","Employee","Project","Other"].map(v=><option key={v}>{v}</option>)}</select></Field>
      <Field label="External Contact"><input name="external_contact" value={form.external_contact} onChange={handleChange} className="input" /></Field>
      <Field label="Responsible Person"><input name="responsible_person" value={form.responsible_person} onChange={handleChange} className="input" /></Field>
      <Field label="Status"><select name="status" value={form.status} onChange={handleChange} className="input">{["New","Under Review","In Progress","Waiting","Completed","Critical"].map(v=><option key={v}>{v}</option>)}</select></Field>
      <Field label="Risk"><select name="risk" value={form.risk} onChange={handleChange} className="input">{["Low","Medium","High"].map(v=><option key={v}>{v}</option>)}</select></Field>
      <Field label="Primary Deadline"><input type="date" name="primary_deadline" value={form.primary_deadline} onChange={handleChange} className="input" /></Field>
      <Field label="Follow-up Date"><input type="date" name="follow_up_date" value={form.follow_up_date} onChange={handleChange} className="input" /></Field>
      <Field label="Description" wide><textarea name="description" value={form.description} onChange={handleChange} rows={4} className="input" /></Field>
      <Field label="Next Action" wide><textarea name="next_action" value={form.next_action} onChange={handleChange} rows={4} className="input" /></Field>
      <div className="md:col-span-2 flex justify-end"><button disabled={submitting || !form.company.trim()} className="rounded-xl bg-slate-950 px-6 py-3 text-sm font-semibold text-white disabled:opacity-50">{submitting ? "Creating..." : "Create case"}</button></div>
    </form>
  </div>;
}
function Field({label, children, wide=false}:{label:string;children:React.ReactNode;wide?:boolean}) { return <label className={wide?"md:col-span-2":""}><span className="mb-2 block text-sm font-medium text-slate-700">{label}</span>{children}</label>; }
