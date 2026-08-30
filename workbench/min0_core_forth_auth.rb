# frozen_string_literal: true

require "openssl"

module Min0CoreForth
  AUTH_DOMAIN = "MIN0-CORE-FORTH-IMAGE-AUTH-R0\0".b
  HMAC_SCHEME = "hmac-sha256"
  ED25519_SCHEME = "ed25519"
  ED25519_PRIVATE_DER_PREFIX = "302e020100300506032b657004220420"
  ED25519_PUBLIC_DER_PREFIX = "302a300506032b6570032100"

  class AuthenticationError < StandardError; end

  module Authentication
    module_function

    def message(identity_sha256)
      unless identity_sha256.is_a?(String) && identity_sha256.match?(/\A[0-9a-f]{64}\z/)
        raise AuthenticationError, "identity must be a lowercase SHA-256 hex String"
      end

      AUTH_DOMAIN + [identity_sha256].pack("H*")
    end

    def hmac_sign(identity_sha256, secret_key)
      unless secret_key.is_a?(String) && secret_key.bytesize >= 32
        raise AuthenticationError, "HMAC-SHA256 key must be at least 32 bytes"
      end

      OpenSSL::HMAC.digest("SHA256", secret_key, message(identity_sha256))
    end

    def hmac_verify(identity_sha256, secret_key, tag)
      return false unless tag.is_a?(String) && tag.bytesize == 32

      expected = hmac_sign(identity_sha256, secret_key)
      OpenSSL.fixed_length_secure_compare(expected, tag)
    rescue AuthenticationError
      false
    end

    def ed25519_private_from_seed(seed)
      unless seed.is_a?(String) && seed.bytesize == 32
        raise AuthenticationError, "Ed25519 seed must be 32 bytes"
      end

      OpenSSL::PKey.read([ED25519_PRIVATE_DER_PREFIX + seed.unpack1("H*")].pack("H*"))
    end

    def ed25519_public_bytes(private_key)
      private_key.public_to_der.byteslice(-32, 32)
    end

    def ed25519_public_from_bytes(public_key)
      return nil unless public_key.is_a?(String) && public_key.bytesize == 32

      OpenSSL::PKey.read([ED25519_PUBLIC_DER_PREFIX + public_key.unpack1("H*")].pack("H*"))
    rescue OpenSSL::PKey::PKeyError
      nil
    end

    def ed25519_sign(identity_sha256, private_key)
      private_key.sign(nil, message(identity_sha256))
    end

    def ed25519_verify(identity_sha256, public_key, signature)
      return false unless signature.is_a?(String) && signature.bytesize == 64

      key = ed25519_public_from_bytes(public_key)
      return false if key.nil?

      key.verify(nil, signature, message(identity_sha256))
    rescue AuthenticationError, OpenSSL::PKey::PKeyError
      false
    end
  end
end
