import { useEffect, useRef, useState } from "react";

import { fetchUpgradePatches, uploadUpgradePatch } from "../api/productClient";

import { FUTURE_PATCHES } from "../product/constants";



type UploadedPatch = {

  upgrade_id: string;

  label: string;

  status?: string;

};



export function UpgradeCenterPage() {

  const [patches, setPatches] = useState<string[]>([...FUTURE_PATCHES]);

  const [uploaded, setUploaded] = useState<UploadedPatch[]>([]);

  const [note, setNote] = useState("Advanced features can be installed through Upgrade Center patches.");

  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  const [uploadError, setUploadError] = useState<string | null>(null);

  const [uploading, setUploading] = useState(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);



  async function refreshPatches() {

    const result = await fetchUpgradePatches();

    if (result.patches?.length) setPatches(result.patches);

    if (result.uploaded_patches?.length) setUploaded(result.uploaded_patches);

    if (result.note) setNote(result.note);

  }



  useEffect(() => {

    void refreshPatches().catch(() => {

      /* fallback to constants */

    });

  }, []);



  async function handleUpload() {

    const file = fileInputRef.current?.files?.[0];

    if (!file) {

      setUploadError("Choose a .zip, .json, or .patch file first.");

      return;

    }

    setUploading(true);

    setUploadError(null);

    setUploadStatus(null);

    try {

      const result = await uploadUpgradePatch(file);

      setUploadStatus(result.message || `Uploaded ${result.filename} (${result.upgrade_id})`);

      if (fileInputRef.current) {

        fileInputRef.current.value = "";

      }

      await refreshPatches();

    } catch (err) {

      setUploadError(err instanceof Error ? err.message : "Upload failed");

    } finally {

      setUploading(false);

    }

  }



  return (

    <div className="product-page">

      <header className="header">

        <div>

          <p className="eyebrow">Upgrade Center</p>

          <h1>Patch-Ready Features</h1>

          <p className="subtitle">{note}</p>

        </div>

      </header>



      <section className="card">

        <h2>Upload Patch Package</h2>

        <p className="muted">Upload stores packages only. Preview, backup, and apply remain required before installation.</p>

        <input ref={fileInputRef} className="filter-input full-width" type="file" accept=".zip,.json,.patch" />

        <button type="button" className="primary-btn" disabled={uploading} onClick={() => void handleUpload()}>

          {uploading ? "Uploading…" : "Upload Patch"}

        </button>

        {uploadStatus && <div className="success-banner">{uploadStatus}</div>}

        {uploadError && <div className="error-banner">{uploadError}</div>}

      </section>



      {uploaded.length > 0 && (

        <section className="card">

          <h2>Uploaded Patches</h2>

          <ul className="patch-list">

            {uploaded.map((patch) => (

              <li key={patch.upgrade_id}>

                {patch.label} <span className="muted">({patch.upgrade_id})</span>

              </li>

            ))}

          </ul>

        </section>

      )}



      <section className="card">

        <h2>Available Future Patches</h2>

        <ul className="patch-list">

          {patches.map((patch) => (

            <li key={patch}>{patch}</li>

          ))}

        </ul>

        <p className="muted">Install patches here in future releases. Core Runway runtime remains unchanged until a patch is applied.</p>

      </section>

    </div>

  );

}

