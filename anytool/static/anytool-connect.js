/**
 * anytool Connect — embeddable widget for end-user OAuth connections.
 *
 * Usage:
 *   <script src="https://your-anytool.com/v1/connect.js"></script>
 *   <script>
 *     AnytoolConnect.init({ apiKey: "at_xxx", baseUrl: "https://your-anytool.com" });
 *
 *     // Open popup for end-user to connect Gmail
 *     AnytoolConnect.open({
 *       provider: "gmail",
 *       userId: "customer-123",
 *       onSuccess: (connection) => console.log("Connected!", connection),
 *       onError: (error) => console.error("Failed:", error),
 *     });
 *   </script>
 *
 * Or as a button:
 *   <button onclick="AnytoolConnect.open({ provider: 'gmail', userId: 'customer-123' })">
 *     Connect Gmail
 *   </button>
 */

(function (global) {
  "use strict";

  var config = {
    apiKey: "",
    baseUrl: "",
  };

  var AnytoolConnect = {
    /**
     * Initialize with your API key.
     * @param {{ apiKey: string, baseUrl?: string }} opts
     */
    init: function (opts) {
      config.apiKey = opts.apiKey;
      config.baseUrl = (opts.baseUrl || "").replace(/\/$/, "");
      if (!config.apiKey) {
        console.error("[anytool] init() requires apiKey");
      }
    },

    /**
     * Open OAuth popup for an end-user to connect an app.
     * @param {{
     *   provider: string,
     *   userId: string,
     *   onSuccess?: (connection: object) => void,
     *   onError?: (error: string) => void,
     *   popupWidth?: number,
     *   popupHeight?: number,
     * }} opts
     */
    open: function (opts) {
      if (!config.apiKey) {
        console.error("[anytool] Call AnytoolConnect.init() first");
        if (opts.onError) opts.onError("Not initialized");
        return;
      }

      var provider = opts.provider;
      var userId = opts.userId;

      if (!provider || !userId) {
        console.error("[anytool] provider and userId are required");
        if (opts.onError) opts.onError("provider and userId are required");
        return;
      }

      // Step 1: Call the API to get the auth URL
      var xhr = new XMLHttpRequest();
      xhr.open("POST", config.baseUrl + "/v1/connections");
      xhr.setRequestHeader("Content-Type", "application/json");
      xhr.setRequestHeader("Authorization", "Bearer " + config.apiKey);

      xhr.onload = function () {
        if (xhr.status !== 200) {
          var errMsg = "Failed to start OAuth";
          try {
            errMsg = JSON.parse(xhr.responseText).detail || errMsg;
          } catch (e) {}
          console.error("[anytool]", errMsg);
          if (opts.onError) opts.onError(errMsg);
          return;
        }

        var data = JSON.parse(xhr.responseText);
        var authUrl = data.auth_url;

        if (!authUrl) {
          if (opts.onError) opts.onError("No auth_url returned");
          return;
        }

        // Step 2: Open popup
        var width = opts.popupWidth || 500;
        var height = opts.popupHeight || 700;
        var left = window.screenX + (window.outerWidth - width) / 2;
        var top = window.screenY + (window.outerHeight - height) / 2;

        var popup = window.open(
          authUrl,
          "anytool_connect",
          "width=" + width +
            ",height=" + height +
            ",left=" + left +
            ",top=" + top +
            ",toolbar=no,menubar=no,scrollbars=yes"
        );

        if (!popup) {
          // Popup blocked — fall back to redirect
          window.location.href = authUrl;
          return;
        }

        // Step 3: Poll for popup close + check connection status
        var pollInterval = setInterval(function () {
          try {
            if (popup.closed) {
              clearInterval(pollInterval);

              // Check if connection is now active
              var checkXhr = new XMLHttpRequest();
              checkXhr.open(
                "GET",
                config.baseUrl +
                  "/v1/connections/check?provider=" +
                  encodeURIComponent(provider) +
                  "&user_id=" +
                  encodeURIComponent(userId)
              );
              checkXhr.setRequestHeader(
                "Authorization",
                "Bearer " + config.apiKey
              );

              checkXhr.onload = function () {
                if (checkXhr.status === 200) {
                  var result = JSON.parse(checkXhr.responseText);
                  if (result.connected) {
                    if (opts.onSuccess)
                      opts.onSuccess({
                        provider: provider,
                        userId: userId,
                        connected: true,
                      });
                  } else {
                    if (opts.onError)
                      opts.onError("User closed popup without connecting");
                  }
                } else {
                  if (opts.onError) opts.onError("Failed to verify connection");
                }
              };

              checkXhr.onerror = function () {
                if (opts.onError) opts.onError("Network error checking connection");
              };

              checkXhr.send();
            }
          } catch (e) {
            // Cross-origin errors while popup is on Google's domain — ignore
          }
        }, 1000);
      };

      xhr.onerror = function () {
        if (opts.onError) opts.onError("Network error");
      };

      xhr.send(JSON.stringify({ provider: provider, user_id: userId }));
    },

    /**
     * Check if a user has connected a specific provider.
     * @param {{ provider: string, userId: string }} opts
     * @returns {Promise<boolean>}
     */
    isConnected: function (opts) {
      return new Promise(function (resolve, reject) {
        var xhr = new XMLHttpRequest();
        xhr.open(
          "GET",
          config.baseUrl +
            "/v1/connections/check?provider=" +
            encodeURIComponent(opts.provider) +
            "&user_id=" +
            encodeURIComponent(opts.userId)
        );
        xhr.setRequestHeader("Authorization", "Bearer " + config.apiKey);

        xhr.onload = function () {
          if (xhr.status === 200) {
            resolve(JSON.parse(xhr.responseText).connected);
          } else {
            reject(new Error("Check failed"));
          }
        };
        xhr.onerror = function () {
          reject(new Error("Network error"));
        };
        xhr.send();
      });
    },
  };

  // Export
  if (typeof module !== "undefined" && module.exports) {
    module.exports = AnytoolConnect;
  }
  global.AnytoolConnect = AnytoolConnect;
})(typeof window !== "undefined" ? window : this);
