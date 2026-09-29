import React from "react";
import useModelStore from "../../store/model.store";
import { X } from "lucide-react";
import Button from "./Button";

import DowngradeModel from "../models/DowngradeModel";
import MailPrompt from "../models/MailPrompt";

const Model = () => {
  const closeModel = useModelStore((state) => state.closeModel);
  const modelData = useModelStore((state) => state.modelData);
  const modelKey = useModelStore((state) => state.modelKey);

  return (
    <>
      {/* Backdrop Overlay */}
      <div
        className="fixed inset-0 z-40 bg-gray-500/30 backdrop-blur-sm transition-opacity duration-300"
      />

      {/* Modal Container */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto transform transition-all duration-300 animate-in fade-in zoom-in-95">
          {/* Modal Header */}
          <div className="sticky top-0 bg-(--accent) px-6 py-4 flex items-center justify-between border-b border-blue-200">
            <div>
              <h2 className="text-2xl font-bold text-white">
                {modelData?.title}
              </h2>
            </div>
            <button
              onClick={closeModel}
              className="p-1 hover:bg-(--danger) rounded-lg transition-colors duration-200 text-white"
              aria-label="Close modal"
              title="Close"
            >
              <X size={24} />
            </button>
          </div>

          {/* Modal Body */}
          <div className="p-6">
            {modelData?.description && (
              <p className="text-gray-600 text-base leading-relaxed mb-6">
                {modelData.description}
              </p>
            )}

            {/* Content Section */}
            {/* <div className="mb-6">{modelKey === "add" && <Add />}</div> */}
            <div className="mb-6">
              {modelKey === 'downgrade' && <DowngradeModel />}
              {modelKey === 'mail-prompt' && <MailPrompt onSubmit={modelData?.onSubmit} />}
            </div>

            {/* Modal Footer */}
            {/* <div className="flex gap-3 justify-end pt-4 border-t border-gray-200">
              <Button title="Cancel" variant="secondary" onClick={closeModel} />
            </div> */}
          </div>
        </div>
      </div>
    </>
  );
};

export default Model;
