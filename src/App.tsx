import { useState } from "react";
import { FileText, FolderOpen, Plus } from "lucide-react";
import PaperWriter from "./components/PaperWriter";

/**
 * thinkstack desktop app shell.
 *
 * provides a sidebar with the paper writer view.
 * the writer opens when the user clicks the writer button.
 */
export default function App() {
  return (
    <div className="app-shell">
      <PaperWriter />
    </div>
  );
}
