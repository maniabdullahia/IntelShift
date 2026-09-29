import { create } from "zustand";

const useModelStore = create((set, get) => ({
  isOpenModel: false,
  modelKey: null,
  modelData: null,
  resolver: null,

  openModel: (key, data = {}) => {
    return new Promise((resolve, reject) => {
      set({
        isOpenModel: true,
        modelKey: key,
        modelData: data,
        resolver: { resolve, reject },
      });
    });
  },

  submitModel: (data) => {
    const resolver = get().resolver;

    if (resolver?.resolve) {
      resolver.resolve(data);
    }

    set({
      isOpenModel: false,
      modelKey: null,
      modelData: null,
      resolver: null,
    });
  },

  closeModel: () => {
    const resolver = get().resolver;

    if (resolver?.reject) {
      resolver.reject(new Error("Modal closed"));
    }

    set({
      isOpenModel: false,
      modelKey: null,
      modelData: null,
      resolver: null,
    });
  },
}));

export default useModelStore;